import asyncio
from uuid import uuid4
from app.services.summarization_service import (
    generate_beginner_summary,
    generate_intermediate_summary,
    generate_advanced_summary
)

# Mock paper data for testing
mock_paper = {
    "paper_id": uuid4(),
    "abstract": """
    Neural networks have revolutionized natural language processing tasks by enabling 
    more effective representation learning and transfer learning capabilities. This study 
    examines the impact of various neural network architectures on downstream NLP tasks 
    including sentiment analysis, named entity recognition, and question answering. 
    Our experiments demonstrate that transformer-based models consistently outperform 
    recurrent neural networks across all evaluation metrics, with particular improvements 
    in tasks requiring long-range dependencies. We propose a novel attention mechanism 
    that further enhances performance on context-heavy tasks by 7.2%. Our findings 
    suggest that architectural innovations focused on attention mechanisms yield the 
    most significant gains in NLP performance.
    """,
    "introduction_chunks": [
        {
            "text": """
            Natural language processing (NLP) has seen remarkable progress in recent years, 
            largely due to advances in neural network architectures. Traditional approaches 
            relied on handcrafted features and shallow models, which limited their ability 
            to capture the complexity of human language. The introduction of deep learning 
            methods, particularly recurrent neural networks (RNNs) and later transformer 
            models, has dramatically improved performance across a wide range of NLP tasks.
            """,
            "metadata": {"is_introduction": True}
        },
        {
            "text": """
            Recent research has focused heavily on attention mechanisms as a way to better 
            model long-range dependencies in text. The transformer architecture, introduced 
            by Vaswani et al. (2017), represents a significant departure from sequential 
            processing models by relying entirely on attention mechanisms. This approach 
            has enabled more effective parallelization during training and has yielded 
            state-of-the-art results on benchmarks like GLUE and SuperGLUE.
            """,
            "metadata": {"is_introduction": True}
        }
    ],
    "conclusion_chunks": [
        {
            "text": """
            Our comprehensive evaluation demonstrates that transformer-based architectures 
            consistently outperform RNN variants across a diverse set of NLP tasks. The 
            performance gap is particularly pronounced in tasks requiring understanding of 
            long-range dependencies and complex contextual relationships. The novel attention 
            mechanism we propose further enhances these capabilities, yielding an average 
            improvement of 7.2% on context-heavy tasks.
            """,
            "metadata": {"is_conclusion": True}
        },
        {
            "text": """
            These findings suggest several directions for future research. First, while 
            attention mechanisms have proven highly effective, they come with significant 
            computational costs that scale quadratically with sequence length. Developing 
            more efficient attention variants remains an important challenge. Second, our 
            results indicate that task-specific architectural modifications can yield 
            substantial gains, suggesting that a one-size-fits-all approach may not be 
            optimal for all NLP applications.
            """,
            "metadata": {"is_conclusion": True}
        }
    ],
    "methodology_chunks": [
        {
            "text": """
            We conducted experiments using three neural network architectures: Long Short-Term 
            Memory networks (LSTM), Gated Recurrent Units (GRU), and Transformer models. All 
            models were implemented using PyTorch and trained on identical datasets to ensure 
            fair comparison. For word representations, we utilized pre-trained GloVe embeddings 
            (Pennington et al., 2014) as input to all models.
            """,
            "metadata": {"is_methodology": True}
        }
    ],
    "results_chunks": [
        {
            "text": """
            Table 1 presents the performance metrics across all evaluated tasks. Transformer 
            models achieved the highest scores on all metrics, with an average F1 score of 
            0.87 compared to 0.79 for LSTMs and 0.78 for GRUs. The performance gap was most 
            pronounced on the question answering task, where transformers outperformed the 
            next best model by 9.3 percentage points.
            """,
            "metadata": {"is_results": True}
        }
    ],
    "discussion_chunks": [
        {
            "text": """
            The superior performance of transformer models can be attributed to their ability 
            to model long-range dependencies more effectively than recurrent architectures. 
            This is particularly important for tasks like question answering and sentiment 
            analysis of longer documents, where relevant information may be distributed across 
            the text. Our proposed attention variant further enhances this capability by 
            incorporating syntactic structure awareness.
            """,
            "metadata": {"is_discussion": True}
        }
    ],
    "full_text": """
    [Full paper text would be here - this is a placeholder for testing purposes. 
    In a real implementation, this would contain the complete text of the paper, 
    including all sections, figures, tables, and references.]
    """
}

async def main():
    """Generate and display summaries at different levels for the mock paper."""
    print("Generating summaries for a sample research paper on neural networks...\n")
    
    # Extract the necessary components from our mock paper data
    abstract = mock_paper["abstract"]
    intro_chunks = mock_paper["introduction_chunks"]
    conclusion_chunks = mock_paper["conclusion_chunks"]
    full_text = mock_paper["full_text"]
    all_chunks = (
        mock_paper["introduction_chunks"] + 
        mock_paper["methodology_chunks"] + 
        mock_paper["results_chunks"] + 
        mock_paper["discussion_chunks"] + 
        mock_paper["conclusion_chunks"]
    )
    
    # Generate beginner summary
    print("=" * 80)
    print("BEGINNER SUMMARY")
    print("=" * 80)
    beginner_summary = await generate_beginner_summary(abstract, intro_chunks, conclusion_chunks)
    print(beginner_summary)
    print("\n")
    
    # Generate intermediate summary
    print("=" * 80)
    print("INTERMEDIATE SUMMARY")
    print("=" * 80)
    intermediate_summary = await generate_intermediate_summary(abstract, intro_chunks, conclusion_chunks)
    print(intermediate_summary)
    print("\n")
    
    # Generate advanced summary
    print("=" * 80)
    print("ADVANCED SUMMARY")
    print("=" * 80)
    advanced_summary = await generate_advanced_summary(abstract, full_text, all_chunks)
    print(advanced_summary)

# Run the async main function
if __name__ == "__main__":
    asyncio.run(main()) 