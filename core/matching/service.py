"""Deterministic store-scoped matching with conservative variant protection."""
from __future__ import annotations
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from dataclasses import dataclass
from core.models.product import Product
from core.repositories import ProductRepo, ProductAliasRepo

@dataclass
class MatchResult:
    product: Product | None
    confidence: float
    method: str
    alternatives: list[Product]

def normalize_text(text: str) -> str:
    text = unicodedata.normalize('NFKC', text or '').casefold().replace('ё','е')
    text = re.sub(r'(?<=\d),(?=\d)', '.', text)
    text = re.sub(r'(\d)\s+(%|мл|кг|гр|л|г)\b', r'\1\2', text)
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s.%/-]', ' ', text)).strip()

def extract_numbers(text: str) -> dict:
    text = normalize_text(text)
    result = {}
    for match in re.finditer(r'(\d+(?:\.\d+)?)\s*(мл|ml|кг|kg|гр|г|g|л|l|%)(?!\w)', text):
        value, unit = float(match[1]), match[2]
        key = 'fat_content' if unit=='%' else ('volume' if unit in ('мл','ml','л','l') else 'weight')
        if unit in ('мл','ml','гр','г','g'):
            value /= 1000
        result[key] = value
    return result

def compatible(a, b):
    left, right = extract_numbers(a), extract_numbers(b)
    return all(abs(left[k]-right[k]) < 0.0001 for k in left.keys() & right.keys())

def signature(text):
    return ' '.join(sorted(normalize_text(text).split()))

def fuzzy_score(a, b):
    if not a or not b or not compatible(a,b):
        return 0.0
    left, right = signature(a), signature(b)
    if left == right:
        return 100.0
    ac, bc = Counter(left.split()), Counter(right.split())
    overlap = sum((ac & bc).values()) / max(sum(ac.values()), sum(bc.values()), 1)
    score = 100 * (0.65 * overlap + 0.35 * SequenceMatcher(None,left,right).ratio())
    # Missing variant attributes prevent automatic selection.
    if extract_numbers(a) != extract_numbers(b):
        score = min(score, 84)
    return round(score, 2)

calculate_similarity = fuzzy_score

class MatchingService:
    def __init__(self, auto_match_threshold=92.0, review_threshold=55.0, max_results=5):
        self.auto_match_threshold = auto_match_threshold
        self.review_threshold = review_threshold
        self.max_results = max_results

    async def match_product(self, store_id, ocr_text, article='', barcode=''):
        # Exact identifiers must be unique inside the store.
        for field, value in [('barcode',barcode), ('article',article)]:
            if value:
                products = await ProductRepo.find_identifier(store_id, field, value)
                if len(products)==1:
                    return MatchResult(products[0],100,field,products)
                if len(products)>1:
                    return MatchResult(None,0,'ambiguous',products[:self.max_results])
        alias = await ProductAliasRepo.find_exact(store_id, normalize_text(ocr_text))
        if alias:
            product = await ProductRepo.get_by_id(alias.product_id)
            if product and product.store_id==store_id and product.is_active:
                return MatchResult(product,100,'alias',[])
        candidates = await ProductRepo.match_candidates(store_id, ocr_text)
        ranked = sorted(((fuzzy_score(ocr_text,p.name),p) for p in candidates), key=lambda pair:pair[0], reverse=True)
        alternatives = [p for score,p in ranked[:self.max_results] if score>=self.review_threshold]
        if not ranked or ranked[0][0]<self.review_threshold:
            return MatchResult(None,0,'none',alternatives)
        score, product = ranked[0]
        if len(ranked)>1 and score-ranked[1][0]<8:
            score = min(score,84)
        return MatchResult(product,score,'exact' if score==100 else 'fuzzy',alternatives)

    async def match_document_items(self, store_id, items):
        results=[]
        for source in items:
            item=dict(source)
            match=await self.match_product(store_id,item.get('ocr_text') or item.get('product_name',''),item.get('article',''),item.get('barcode',''))
            automatic=match.product and match.confidence>=self.auto_match_threshold
            if automatic and item.get('unit') and match.product.unit:
                automatic=normalize_text(item['unit']).rstrip('.')==normalize_text(match.product.unit).rstrip('.')
            item.update(product_id=match.product.id if automatic else None, confidence=match.confidence,
                        match_status='matched' if automatic else ('needs_review' if match.product else 'not_found'))
            if automatic:
                item.update(product_name=match.product.name,article=match.product.article or '',barcode=match.product.barcode or '',unit=match.product.unit or item.get('unit',''))
            item['alternatives']=[p.to_dict() for p in match.alternatives]
            results.append(item)
        return results
