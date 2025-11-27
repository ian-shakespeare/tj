import pdfplumber

from io import BytesIO
from pdfplumber.page import Page
from sentence_transformers import SentenceTransformer
from typing import Generator

from .models import Chunk, Document

CHUNK_SIZE = 512
CHUNK_OVERLAP = 128
EMBEDDER = SentenceTransformer("all-MiniLM-L6-v2")


def decode_pdf(file: BytesIO) -> str:
    pdf = pdfplumber.open(file)

    pages = map(Page.extract_text, pdf.pages)
    content = "\r\n".join(pages)

    pdf.close()
    return content


def chunks(content: str) -> Generator[str]:
    cursor = 0
    while True:
        if cursor + CHUNK_SIZE > len(content):
            yield content[cursor:cursor+CHUNK_SIZE]
            break

        yield content[cursor:cursor+CHUNK_SIZE]
        cursor += CHUNK_SIZE - CHUNK_OVERLAP


def ingest_document(name: str, body: BytesIO):
    document = Document(name=name)
    document.save()

    decoded = decode_pdf(body)
    for position, content in enumerate(chunks(decoded)):
        embedding = EMBEDDER.encode(content)
        chunk = Chunk(content=content, position=position,
                      embedding=embedding, document=document)
        chunk.save()

    print(f"### Finished Ingesting Document '{name}' ###")
