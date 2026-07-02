"""Ensure LangChain packages required at runtime are installed (Azure pip deploy)."""


def test_langchain_openai_imports() -> None:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import Runnable
    from langchain_openai import AzureChatOpenAI

    assert ChatPromptTemplate is not None
    assert Runnable is not None
    assert AzureChatOpenAI is not None


def test_langchain_openai_transitive_deps() -> None:
    import tiktoken

    assert tiktoken is not None
