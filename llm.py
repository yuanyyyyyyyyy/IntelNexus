import re
import openai
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from llm_utils import _common_llm_params, resolve_model_config, get_model_choices
from config import OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY
import logging
import re

import warnings

warnings.filterwarnings("ignore")


def get_llm(model_choice):
    # Look up the configuration (cloud or local Ollama)
    config = resolve_model_config(model_choice)

    if config is None:  # Extra error check
        supported_models = get_model_choices()
        raise ValueError(
            f"Unsupported LLM model: '{model_choice}'. "
            f"Supported models (case-insensitive match) are: {', '.join(supported_models)}"
        )

    # Extract the necessary information from the configuration
    llm_class = config["class"]
    model_specific_params = config["constructor_params"]

    # Combine common parameters with model-specific parameters
    # Model-specific parameters will override common ones if there are any conflicts
    all_params = {**_common_llm_params, **model_specific_params}

    # Create the LLM instance using the gathered parameters
    llm_instance = llm_class(**all_params)

    return llm_instance


def refine_query(llm, user_input):
    system_prompt = """
    You are a Network Intelligence Analyst. Your task is to refine the provided user query for optimal search results across multiple sources including academic papers, news articles, social media, and web content.
    
    Rules:
    1. Analyze the user query and improve it for better search results
    2. Refine by adding or removing words to get the best results
    3. Don't use any logical operators (AND, OR, etc.)
    4. Output just the refined query and nothing else

    INPUT:
    """
    prompt_template = ChatPromptTemplate(
        [("system", system_prompt), ("user", "{query}")]
    )
    chain = prompt_template | llm | StrOutputParser()
    return chain.invoke({"query": user_input})


def filter_results(llm, query, results):
    if not results:
        return []

    system_prompt = """
    You are a Network Intelligence Analyst. You are given a search query and a list of search results from multiple sources (academic papers, news, social media, web).
    Your task is to select the Top 20 most relevant results that best match the search query.
    Rule:
    1. Output ONLY at most top 20 indices (comma-separated list) that best match the input query

    Search Query: {query}
    Search Results:
    """

    final_str = _generate_final_string(results)

    prompt_template = ChatPromptTemplate(
        [("system", system_prompt), ("user", "{results}")]
    )
    chain = prompt_template | llm | StrOutputParser()
    try:
        result_indices = chain.invoke({"query": query, "results": final_str})
    except openai.RateLimitError as e:
        print(
            f"Rate limit error: {e} \n Truncating to Web titles only with 30 characters"
        )
        final_str = _generate_final_string(results, truncate=True)
        result_indices = chain.invoke({"query": query, "results": final_str})

    # Select top_k results using original (non-truncated) results
    parsed_indices = []
    for match in re.findall(r"\d+", result_indices):
        try:
            idx = int(match)
            if 1 <= idx <= len(results):
                parsed_indices.append(idx)
        except ValueError:
            continue

    # Remove duplicates while preserving order
    seen = set()
    parsed_indices = [
        i for i in parsed_indices if not (i in seen or seen.add(i))
    ]

    if not parsed_indices:
        logging.warning(
            "Unable to interpret LLM result selection ('%s'). "
            "Defaulting to the top %s results.",
            result_indices,
            min(len(results), 20),
        )
        parsed_indices = list(range(1, min(len(results), 20) + 1))

    top_results = [results[i - 1] for i in parsed_indices[:20]]

    return top_results


def _generate_final_string(results, truncate=False):
    """
    Generate a formatted string from the search results for LLM processing.
    """

    if truncate:
        max_title_length = 30
        max_link_length = 0

    final_str = []
    for i, res in enumerate(results):
        title = res.get("title", "")
        link = res.get("link", "") or res.get("url", "") or res.get("pdf_url", "")
        
        title = re.sub(r"[^0-9a-zA-Z\-\.\s]", " ", str(title))
        link = re.sub(r"(?<=\.onion).*", "", str(link))
        
        if not link and not title:
            continue

        if truncate:
            title = title[:max_title_length] + "..." if len(title) > max_title_length else title
            link = link[:max_link_length] + "..." if len(link) > max_link_length else link

        final_str.append(f"{i+1}. {link} - {title}")

    return "\n".join(s for s in final_str)


def generate_summary(llm, query, content):
    system_prompt = """
You are a Senior Network Intelligence Analyst tasked with generating comprehensive, professional-grade analysis from multi-source search results.

## Your Task
Generate a detailed, multi-angle intelligence report based on search results from:
- Academic papers and research
- News articles
- Social media discussions
- Web content

## Requirements
1. **Executive Summary**: Start with a brief overview of the topic (2-3 sentences)
2. **Background**: Provide context and background on the topic
3. **Key Findings**: Detail all significant findings from each source type
4. **Source Analysis**: Analyze each source type separately:
   - Academic: Research trends, key papers, expert opinions
   - News: Latest developments, key events, timeline
   - Social: Public sentiment, discussions, trends
   - Web: General information, resources, tools
5. **Deep Analysis**: Provide in-depth analysis of the most important aspects
6. **Data & Statistics**: Extract any relevant numbers, dates, percentages
7. **Expert Perspectives**: Summarize expert opinions and quotes
8. **Implications**: Discuss implications and significance
9. **Conclusions**: Provide a comprehensive conclusion
10. **References**: List all source URLs11. **Further Research**: Suggest areas used
 for deeper investigation

## Format Guidelines
- Use clear hierarchical headings (## for main sections, ### for subsections)
- Be thorough - this is a professional intelligence report
- Include specific details, dates, names, and statistics
- Reference source links throughout
- Write in formal, professional tone

Generate a comprehensive report with substantial content (aim for 3000+ words).
"""
    prompt_template = ChatPromptTemplate(
        [("system", system_prompt), ("user", "{content}")]
    )
    chain = prompt_template | llm | StrOutputParser()
    return chain.invoke({"query": query, "content": content})
