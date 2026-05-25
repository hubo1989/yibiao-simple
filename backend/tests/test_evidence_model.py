"""证据引用模型测试"""
from app.models.evidence import EvidenceSourceType, EvidenceRef


class TestEvidenceSourceType:
    def test_enum_values(self):
        assert EvidenceSourceType.tender_document.value == "tender_document"
        assert EvidenceSourceType.knowledge_doc.value == "knowledge_doc"
        assert EvidenceSourceType.material_asset.value == "material_asset"
        assert EvidenceSourceType.manual_input.value == "manual_input"
        assert EvidenceSourceType.generated_content.value == "generated_content"

    def test_all_values(self):
        values = [e.value for e in EvidenceSourceType]
        assert len(values) == 5


class TestEvidenceRefInstantiation:
    def test_create_instance(self):
        ref = EvidenceRef(
            source_type=EvidenceSourceType.knowledge_doc,
            source_id="doc-123",
            source_title="企业资质手册",
            source_location="第3页",
            quote="公司持有ISO9001认证证书",
            relation="用于支撑技术方案中资质部分",
        )
        assert ref.source_type == EvidenceSourceType.knowledge_doc
        assert ref.source_id == "doc-123"
        assert ref.source_title == "企业资质手册"
        assert ref.quote == "公司持有ISO9001认证证书"
        assert ref.relation == "用于支撑技术方案中资质部分"
