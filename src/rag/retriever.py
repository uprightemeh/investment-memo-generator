"""
Retrieval over chunked filings.

Uses TF-IDF + cosine similarity (scikit-learn) rather than a neural
embedding model. This is a deliberate scope decision, not a corner cut:
TF-IDF works well for this use case because filing language is
domain-specific and keyword-heavy (e.g. a query like "supply chain
disruption risk" mostly wins on lexical overlap with the actual risk
factor text), it has zero external model download / API cost, and it
keeps the project runnable completely offline.

If you want to extend this: swapping in `sentence-transformers` embeddings
is a ~20 line change confined to this file, since everything else consumes
DocumentChunk / the ranked chunk list and doesn't care how ranking happened.
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from src.models.schemas import DocumentChunk


class ChunkRetriever:
    def __init__(self, chunks: list[DocumentChunk]):
        self.chunks = chunks
        self._vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
        texts = [c.text for c in chunks]
        self._matrix = self._vectorizer.fit_transform(texts) if texts else None

    def retrieve(self, query: str, top_k: int = 5) -> list[DocumentChunk]:
        """Return the top_k chunks most relevant to `query`, ranked by
        cosine similarity of TF-IDF vectors."""
        if self._matrix is None or not self.chunks:
            return []
        query_vec = self._vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self._matrix)[0]
        ranked_indices = scores.argsort()[::-1][:top_k]
        return [self.chunks[i] for i in ranked_indices if scores[i] > 0]

    def retrieve_by_section(self, section: str) -> list[DocumentChunk]:
        """Retrieve every chunk tagged with a given section verbatim --
        useful when you want the whole Risk Factors section rather than a
        similarity-ranked subset."""
        return [c for c in self.chunks if c.section == section]
