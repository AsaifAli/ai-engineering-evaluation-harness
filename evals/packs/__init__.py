from .base import EvalPack
from .rag import PACK as RAG_PACK
from .code_modernization import PACK as CODE_MODERNIZATION_PACK
from .document_intelligence import PACK as DOCUMENT_INTELLIGENCE_PACK
from .browser_qa import PACK as BROWSER_QA_PACK
from .agent_workflow import PACK as AGENT_WORKFLOW_PACK

PACKS = {
    pack.name: pack
    for pack in (
        RAG_PACK,
        CODE_MODERNIZATION_PACK,
        DOCUMENT_INTELLIGENCE_PACK,
        BROWSER_QA_PACK,
        AGENT_WORKFLOW_PACK,
    )
}
