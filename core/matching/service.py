from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from core.models.product import Product
from core.models.product_alias import ProductAlias
from core.repositories import ProductRepo, ProductAliasRepo


@dataclass
class MatchResult:
    product: Product | None
    confidence: float
    method: str  # alias, exact, fuzzy, article, barcode
    alternatives: list[Product]


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = unicodedata.normalize("NFKC", text)
    text = text.replace(",", ".").replace(";", ".")
    text = re.sub(r"[^\w\s\.\-/%]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_numbers(text: str) -> dict:
    result = {}
    weight_match = re.search(r"(\d+[\.,]?\d*)\s*(?:кг|kg)", text, re.IGNORECASE)
    if weight_match:
        result["weight"] = float(weight_match.group(1).replace(",", "."))

    volume_match = re.search(r"(\d+[\.,]?\d*)\s*(?:л|l|мл|ml)", text, re.IGNORECASE)
    if volume_match:
        val = float(volume_match.group(1).replace(",", "."))
        unit = volume_match.group(0).lower()
        if "мл" in unit or "ml" in unit:
            val /= 1000
        result["volume"] = val

    fat_match = re.search(r"(\d+[\.,]?\d*)\s*%", text)
    if fat_match:
        result["fat_content"] = float(fat_match.group(1).replace(",", "."))

    return result


def calculate_similarity(a: str, b: str) -> float:
    a_norm = normalize_text(a)
    b_norm = normalize_text(b)

    if a_norm == b_norm:
        return 100.0

    a_words = set(a_norm.split())
    b_words = set(b_norm.split())

    if not a_words or not b_words:
        return 0.0

    intersection = a_words & b_words
    union = a_words | b_words
    jaccard = len(intersection) / len(union) if union else 0.0

    a_chars = set(a_norm.replace(" ", ""))
    b_chars = set(b_norm.replace(" ", ""))
    char_intersection = a_chars & b_chars
    char_union = a_chars | b_chars
    char_jaccard = len(char_intersection) / len(char_union) if char_union else 0.0

    longest = max(len(a_norm), len(b_norm))
    common_prefix = 0
    for ca, cb in zip(a_norm, b_norm):
        if ca == cb:
            common_prefix += 1
        else:
            break
    prefix_ratio = common_prefix / longest if longest else 0.0

    score = (jaccard * 40) + (char_jaccard * 30) + (prefix_ratio * 30)
    return min(score, 100.0)


def fuzzy_score(ocr_text: str, product_name: str) -> float:
    ocr_norm = normalize_text(ocr_text)
    prod_norm = normalize_text(product_name)

    if ocr_norm == prod_norm:
        return 100.0

    ocr_words = ocr_norm.split()
    prod_words = prod_norm.split()

    if not ocr_words or not prod_words:
        return 0.0

    matched = 0
    for ow in ocr_words:
        for pw in prod_words:
            if ow == pw:
                matched += 1
                break
            ow_clean = re.sub(r"[^\w]", "", ow)
            pw_clean = re.sub(r"[^\w]", "", pw)
            if ow_clean and pw_clean and (ow_clean in pw_clean or pw_clean in ow_clean):
                matched += 0.5
                break

    word_score = (matched / len(prod_words)) * 70 if prod_words else 0

    ocr_numbers = extract_numbers(ocr_text)
    prod_numbers = extract_numbers(product_name)
    numeric_score = 0
    if ocr_numbers and prod_numbers:
        numeric_matches = 0
        for key in ocr_numbers:
            if key in prod_numbers:
                if abs(ocr_numbers[key] - prod_numbers[key]) < 0.01:
                    numeric_matches += 1
        numeric_score = (numeric_matches / max(len(ocr_numbers), 1)) * 30
    elif not ocr_numbers and not prod_numbers:
        numeric_score = 20

    return min(word_score + numeric_score, 100.0)


class MatchingService:
    def __init__(
        self,
        auto_match_threshold: float = 85.0,
        review_threshold: float = 60.0,
        max_results: int = 5,
    ):
        self.auto_match_threshold = auto_match_threshold
        self.review_threshold = review_threshold
        self.max_results = max_results

    async def match_product(
        self, store_id: int, ocr_text: str, article: str = "", barcode: str = ""
    ) -> MatchResult:
        if barcode:
            products = await ProductRepo.search(store_id, barcode, limit=5)
            if products:
                for p in products:
                    if p.barcode and normalize_text(p.barcode) == normalize_text(barcode):
                        return MatchResult(
                            product=p, confidence=100.0, method="barcode", alternatives=products
                        )

        if article:
            products = await ProductRepo.search(store_id, article, limit=5)
            if products:
                for p in products:
                    if p.article and normalize_text(p.article) == normalize_text(article):
                        return MatchResult(
                            product=p, confidence=100.0, method="article", alternatives=products
                        )

        normalized = normalize_text(ocr_text)
        alias = await ProductAliasRepo.find_exact(store_id, normalized)
        if alias and alias.product_id:
            product = await ProductRepo.get_by_id(alias.product_id)
            if product:
                return MatchResult(
                    product=product,
                    confidence=alias.confidence,
                    method="alias",
                    alternatives=[],
                )

        products = await ProductRepo.search_by_name(store_id, ocr_text, limit=20)
        if not products:
            products = await ProductRepo.search(store_id, ocr_text, limit=20)

        scored: list[tuple[float, Product]] = []
        for p in products:
            score = fuzzy_score(ocr_text, p.name)
            if article and p.article:
                art_score = calculate_similarity(article, p.article)
                score = max(score, art_score)
            if barcode and p.barcode:
                if normalize_text(barcode) == normalize_text(p.barcode):
                    score = 100.0
            scored.append((score, p))

        scored.sort(key=lambda x: x[0], reverse=True)
        alternatives = [p for _, p in scored[:self.max_results]]

        if scored and scored[0][0] >= self.auto_match_threshold:
            return MatchResult(
                product=scored[0][1],
                confidence=scored[0][0],
                method="fuzzy",
                alternatives=alternatives,
            )

        if scored and scored[0][0] >= self.review_threshold:
            return MatchResult(
                product=scored[0][1],
                confidence=scored[0][0],
                method="fuzzy",
                alternatives=alternatives,
            )

        return MatchResult(
            product=None,
            confidence=scored[0][0] if scored else 0.0,
            method="none",
            alternatives=alternatives,
        )

    async def match_document_items(
        self, store_id: int, items: list[dict]
    ) -> list[dict]:
        results = []
        for item in items:
            ocr_text = item.get("product_name", "") or item.get("ocr_text", "")
            article = item.get("article", "")
            barcode = item.get("barcode", "")

            match = await self.match_product(store_id, ocr_text, article, barcode)

            if match.product:
                item["product_id"] = match.product.id
                item["product_name"] = match.product.name
                item["confidence"] = match.confidence
                if match.confidence >= self.auto_match_threshold:
                    item["match_status"] = "matched"
                elif match.confidence >= self.review_threshold:
                    item["match_status"] = "needs_review"
                else:
                    item["match_status"] = "not_found"
            else:
                item["product_id"] = None
                item["confidence"] = match.confidence
                item["match_status"] = "not_found"

            item["alternatives"] = [p.to_dict() for p in match.alternatives]
            results.append(item)

        return results
