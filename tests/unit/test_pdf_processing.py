import asyncio
from app.services.arxiv_service import download_and_process_paper
from uuid import uuid4

async def test_pdf_processing():
    paper_id = uuid4()
    print(f'Testing PDF processing with paper ID: {paper_id}')
    
    try:
        full_text, chunks = await download_and_process_paper('2303.08774', paper_id)
        print(f'Successfully processed PDF. Got {len(chunks)} chunks.')
        print(f'First chunk: {chunks[0]}')
    except Exception as e:
        print(f'Error processing PDF: {str(e)}')

if __name__ == "__main__":
    asyncio.run(test_pdf_processing()) 