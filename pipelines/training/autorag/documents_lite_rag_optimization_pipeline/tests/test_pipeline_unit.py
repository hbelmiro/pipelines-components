"""Unit tests for the documents_lite_rag_optimization_pipeline pipeline."""

from ..pipeline import documents_lite_rag_optimization_pipeline


class TestDocumentsLiteRagOptimizationPipelineUnit:
    """Unit tests for pipeline structure and interface."""

    def test_pipeline_is_callable(self):
        """Pipeline is a GraphComponent (callable with _component_inputs)."""
        assert callable(documents_lite_rag_optimization_pipeline)
        assert hasattr(documents_lite_rag_optimization_pipeline, "_component_inputs")

    def test_pipeline_required_parameters(self):
        """Pipeline declares expected required parameters (Lite: chat/embedding URLs and tokens)."""
        inputs = getattr(documents_lite_rag_optimization_pipeline, "_component_inputs", set())
        assert "test_data_secret_name" in inputs
        assert "test_data_bucket_name" in inputs
        assert "test_data_key" in inputs
        assert "input_data_secret_name" in inputs
        assert "input_data_bucket_name" in inputs
        assert "input_data_key" in inputs
        assert "chat_model_url" in inputs
        assert "chat_model_token" in inputs
        assert "embedding_model_url" in inputs
        assert "embedding_model_token" in inputs
