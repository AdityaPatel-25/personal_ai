import pytest
from backend.rag import chunk_text


def test_chunk_text_empty_input_handled():
    """Verify that empty, whitespace, and newline-only inputs return empty chunk lists."""
    assert chunk_text("") == []
    assert chunk_text("   ") == []
    assert chunk_text("\n\n\n\t  \n") == []


def test_chunk_text_respects_chunk_size():
    """Verify that chunk_text creates multiple chunks respecting the target chunk_size."""
    paragraphs = [
        f"Paragraph {i}: " + ("Algorithmic problem solving requires understanding invariants. " * 3)
        for i in range(1, 10)
    ]
    sample_text = "\n\n".join(paragraphs)

    chunk_size = 350
    chunk_overlap = 60
    chunks = chunk_text(sample_text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    assert len(chunks) > 1, "Should split multi-paragraph text into multiple chunks"

    for chunk in chunks:
        assert "text" in chunk
        assert "metadata" in chunk
        assert "id" in chunk
        text_len = len(chunk["text"])
        assert chunk["metadata"]["char_length"] == text_len
        # The assembling logic accumulates blocks and flushes when exceeding target size
        assert text_len <= chunk_size + 150, f"Chunk exceeded target size substantially: {text_len}"


def test_chunk_text_overlap_carries_over():
    """Verify that consecutive chunks contain overlapping content."""
    paragraphs = [
        "First section: Binary search operates on monotonically sorted collections.",
        "Second section: The two pointer technique converges from opposite boundaries.",
        "Third section: Sliding window maintains validity while expanding right pointer.",
        "Fourth section: Fast and slow pointers detect cycles in linked lists.",
        "Fifth section: Disjoint Set Union tracks connected components with path compression.",
    ]
    sample_text = "\n\n".join(paragraphs)

    chunks = chunk_text(sample_text, chunk_size=180, chunk_overlap=90)
    assert len(chunks) >= 2, "Need at least 2 chunks to verify overlap"

    overlap_found = False
    for i in range(len(chunks) - 1):
        chunk1_text = chunks[i]["text"]
        chunk2_text = chunks[i + 1]["text"]

        chunk1_lines = [line.strip() for line in chunk1_text.splitlines() if line.strip()]
        for line in chunk1_lines:
            if line in chunk2_text:
                overlap_found = True
                break

    assert overlap_found, "Overlap text did not carry over between consecutive chunks"


def test_chunk_text_code_blocks_not_split_mid_line():
    """Verify that multi-line code blocks are preserved line-by-line and never cut mid-line."""
    code_block = (
        "def binary_search(nums, target):\n"
        "    low = 0\n"
        "    high = len(nums) - 1\n"
        "    while low <= high:\n"
        "        mid = low + (high - low) // 2\n"
        "        if nums[mid] == target:\n"
        "            return mid\n"
        "        elif nums[mid] < target:\n"
        "            low = mid + 1\n"
        "        else:\n"
        "            high = mid - 1\n"
        "    return -1"
    )

    intro = "Here is the standard binary search implementation in Python:\n\n"
    outro = "\n\nAlways ensure high is updated to mid - 1 to guarantee termination."
    full_text = intro + code_block + outro

    # Use a small chunk size to force chunking across the code block
    chunks = chunk_text(full_text, chunk_size=160, chunk_overlap=40)

    assert len(chunks) >= 1

    expected_stripped_code_lines = {
        line.strip() for line in code_block.splitlines() if line.strip()
    }

    # Every code line that appears in any chunk must match an entire expected line,
    # rather than being arbitrarily cut in the middle of a token or keyword
    for chunk in chunks:
        chunk_lines = [l.strip() for l in chunk["text"].splitlines() if l.strip()]
        for c_line in chunk_lines:
            if any(
                token in c_line
                for token in [
                    "def binary_search",
                    "low = 0",
                    "high = len",
                    "while low",
                    "mid =",
                    "nums[mid]",
                    "return -1",
                ]
            ):
                assert (
                    c_line in expected_stripped_code_lines
                ), f"Code line was split mid-line: '{c_line}'"
