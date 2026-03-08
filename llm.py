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
    You are a Network Intelligence Analyst tasked with generating comprehensive analysis from multi-source search results.

    Rules:
    1. Analyze data from academic papers, news articles, social media, and web sources
    2. Reference all source links used in the analysis
    3. Provide detailed, evidence-based analysis of the information
    4. Identify key themes, trends, and patterns across different sources
    5. When relevant, extract technical artifacts (names, organizations, dates, statistics)
    6. Generate 3-5 key insights based on the data
    7. Each insight should be specific, actionable, context-based, and data-driven
    8. Include suggested next steps for further research
    9. Be objective and analytical in your assessment
    10. Organize results by source type (academic, news, social, web) when relevant

    Output Format:
    1. Input Query: {query}
    2. Source Links Referenced - all source links used for analysis
    3. Key Insights (3-5 points)
    4. Source Analysis - breakdown by source type
    5. Next Steps - suggested further research directions

    Format your response in a structured way with clear section headings.

    INPUT:
    """
    prompt_template = ChatPromptTemplate(
        [("system", system_prompt), ("user", "{content}")]
    )
    chain = prompt_template | llm | StrOutputParser()
    return chain.invoke({"query": query, "content": content})
