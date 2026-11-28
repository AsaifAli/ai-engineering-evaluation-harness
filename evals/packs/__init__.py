from .base import EvalPack
from .rag import PACK as RAG_PACK
from .document_intelligence import PACK as DOCUMENT_INTELLIGENCE_PACK
from .workflow_orchestration import PACK as WORKFLOW_ORCHESTRATION_PACK
from .safety import PACK as SAFETY_PACK

PACKS = {
    RAG_PACK.name: RAG_PACK,
    DOCUMENT_INTELLIGENCE_PACK.name: DOCUMENT_INTELLIGENCE_PACK,
    WORKFLOW_ORCHESTRATION_PACK.name: WORKFLOW_ORCHESTRATION_PACK,
    SAFETY_PACK.name: SAFETY_PACK,
}
