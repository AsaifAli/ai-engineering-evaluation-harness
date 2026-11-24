from .base import EvalPack
from .rag import PACK as RAG_PACK
from .document_intelligence import PACK as DOCUMENT_INTELLIGENCE_PACK

PACKS = {
    RAG_PACK.name: RAG_PACK,
    DOCUMENT_INTELLIGENCE_PACK.name: DOCUMENT_INTELLIGENCE_PACK,
}
