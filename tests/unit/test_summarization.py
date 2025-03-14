import pytest
from app.services.summarization_service import (
    generate_summaries,
    generate_beginner_summary,
    generate_intermediate_summary,
    generate_advanced_summary
)
from uuid import uuid4


@pytest.fixture
def mock_paper_data():
    """Provide mock paper data for testing summaries."""
    return {
        "paper_id": uuid4(),
        "abstract": "This study investigates the impact of neural networks on natural language processing tasks. We examine multiple architectures and evaluate their performance on benchmark datasets. Our results indicate significant improvements over traditional methods, particularly for complex language understanding tasks.",
        "full_text": "Introduction: Neural networks have revolutionized the field of natural language processing (NLP) in recent years. These powerful models have demonstrated unprecedented capabilities in understanding and generating human language. In this paper, we investigate several neural network architectures and their performance on standard NLP benchmarks. Methods: We evaluated three different architectures: Recurrent Neural Networks (RNNs), Convolutional Neural Networks (CNNs), and Transformers. Each model was trained on a dataset of 10,000 labeled examples and evaluated on a held-out test set. We measured performance using precision, recall, and F1 scores. Results: Our experiments show that Transformer models achieved the highest performance with an F1 score of 92.3% (p-value < 0.01), compared to 85.7% for CNNs and 79.4% for RNNs. Discussion: These results suggest that the self-attention mechanism in Transformers is particularly well-suited for capturing long-range dependencies in text. Limitations include computational requirements and the need for large training datasets. Future research should explore more efficient training methods and applications to low-resource languages.",
        "chunks": [
            {
                "text": "Neural networks have revolutionized the field of natural language processing (NLP) in recent years. These powerful models have demonstrated unprecedented capabilities in understanding and generating human language. In this paper, we investigate several neural network architectures and their performance on standard NLP benchmarks.",
                "metadata": {"is_introduction": True}
            },
            {
                "text": "We evaluated three different architectures: Recurrent Neural Networks (RNNs), Convolutional Neural Networks (CNNs), and Transformers. Each model was trained on a dataset of 10,000 labeled examples and evaluated on a held-out test set. We measured performance using precision, recall, and F1 scores.",
                "metadata": {"is_methodology": True}
            },
            {
                "text": "Our experiments show that Transformer models achieved the highest performance with an F1 score of 92.3% (p-value < 0.01), compared to 85.7% for CNNs and 79.4% for RNNs.",
                "metadata": {"is_results": True}
            },
            {
                "text": "These results suggest that the self-attention mechanism in Transformers is particularly well-suited for capturing long-range dependencies in text. Limitations include computational requirements and the need for large training datasets.",
                "metadata": {"is_discussion": True}
            },
            {
                "text": "Future research should explore more efficient training methods and applications to low-resource languages.",
                "metadata": {"is_conclusion": True}
            }
        ]
    }


def test_generate_beginner_summary(mock_paper_data):
    """Test generating a beginner-friendly summary."""
    summary = generate_beginner_summary(
        mock_paper_data["abstract"],
        [c for c in mock_paper_data["chunks"] if c["metadata"].get("is_introduction")],
        [c for c in mock_paper_data["chunks"] if c["metadata"].get("is_conclusion")]
    )
    
    # Check that the summary exists and has reasonable content
    assert summary is not None
    assert len(summary) > 100
    assert "neural networks" in summary.lower() or "neural network" in summary.lower()
    
    # Ensure the summary is at an appropriate level
    assert "understand" in summary.lower()
    print(f"\nBeginner Summary:\n{summary}")


def test_generate_intermediate_summary(mock_paper_data):
    """Test generating an intermediate-level summary."""
    summary = generate_intermediate_summary(
        mock_paper_data["abstract"],
        [c for c in mock_paper_data["chunks"] if c["metadata"].get("is_introduction")],
        [c for c in mock_paper_data["chunks"] if c["metadata"].get("is_conclusion")]
    )
    
    # Check that the summary exists and has reasonable structure
    assert summary is not None
    assert len(summary) > 200
    assert "## Overview" in summary
    assert "## Methodology" in summary
    
    # Check that it maintains more technical details than beginner
    assert "neural networks" in summary.lower() or "neural network" in summary.lower()
    assert "nlp" in summary.lower() or "natural language processing" in summary.lower()
    print(f"\nIntermediate Summary:\n{summary}")


def test_generate_advanced_summary(mock_paper_data):
    """Test generating an advanced technical summary."""
    summary = generate_advanced_summary(
        mock_paper_data["abstract"],
        mock_paper_data["full_text"],
        mock_paper_data["chunks"]
    )
    
    # Check that the summary exists and has detailed technical structure
    assert summary is not None
    assert len(summary) > 300
    assert "# Technical Research Summary" in summary
    assert "## Methodological Approach" in summary
    assert "## Key Findings" in summary
    
    # Check that it maintains full technical detail
    assert "neural networks" in summary.lower()
    assert "recurrent neural networks" in summary.lower() or "rnns" in summary.lower()
    assert "transformers" in summary.lower()
    assert "p-value" in summary.lower() or "f1 score" in summary.lower()
    print(f"\nAdvanced Summary:\n{summary}")


def test_generate_summaries_function(mock_paper_data):
    """Test the main generate_summaries function."""
    summaries = generate_summaries(
        mock_paper_data["paper_id"],
        mock_paper_data["abstract"],
        mock_paper_data["full_text"],
        mock_paper_data["chunks"]
    )
    
    # This should run asynchronously, so we need to await it
    import asyncio
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(summaries)
    
    # Check that all summary levels are present
    assert result.beginner is not None
    assert result.intermediate is not None
    assert result.advanced is not None
    
    # Check each level has appropriate content
    assert len(result.beginner) > 100
    assert len(result.intermediate) > 200
    assert len(result.advanced) > 300
    print(f"\nAll Summaries:\nBeginner length: {len(result.beginner)}")
    print(f"Intermediate length: {len(result.intermediate)}")
    print(f"Advanced length: {len(result.advanced)}")


def test_all_summary_levels(mock_paper_data):
    """Test all summary levels and print their content for inspection."""
    # Generate all summary levels
    beginner = generate_beginner_summary(
        mock_paper_data["abstract"],
        [c for c in mock_paper_data["chunks"] if c["metadata"].get("is_introduction")],
        [c for c in mock_paper_data["chunks"] if c["metadata"].get("is_conclusion")]
    )
    
    intermediate = generate_intermediate_summary(
        mock_paper_data["abstract"],
        [c for c in mock_paper_data["chunks"] if c["metadata"].get("is_introduction")],
        [c for c in mock_paper_data["chunks"] if c["metadata"].get("is_conclusion")]
    )
    
    advanced = generate_advanced_summary(
        mock_paper_data["abstract"],
        mock_paper_data["full_text"],
        mock_paper_data["chunks"]
    )
    
    # Concatenate all summaries with clear headers into a message
    full_output = "\n\n===== BEGINNER SUMMARY =====\n\n"
    full_output += beginner
    
    full_output += "\n\n===== INTERMEDIATE SUMMARY =====\n\n"
    full_output += intermediate
    
    full_output += "\n\n===== ADVANCED SUMMARY =====\n\n"
    full_output += advanced
    
    # Skip this test but display the message with all summaries
    # This ensures the summaries are shown in the test output
    print(full_output)
    
    # Check key elements of each summary (maintain assertions from other tests)
    assert len(beginner) > 100
    assert "neural networks" in beginner.lower() or "neural network" in beginner.lower()
    
    assert len(intermediate) > 200
    assert "## Overview" in intermediate
    assert "## Methodology" in intermediate
    
    assert len(advanced) > 300
    assert "# Technical Research Summary" in advanced
    assert "## Methodological Approach" in advanced 