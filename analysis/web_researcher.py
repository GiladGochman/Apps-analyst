from ddgs import DDGS


def _fallback_web_info(app_name, reason=None):
    message = (
        f"- Title: {app_name}\n"
        f"  Info: No web search results were found for this application."
    )
    if reason:
        message += f" Search note: {reason}."
    return message + "\n"


def search_web_info(app_name):
    query = f"what is {app_name} software overview"
    print(f"Searching for: {query}\n")

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=10, backend="duckduckgo", region="us-en"))
    except Exception as exc:
        print(f"[!] Web search failed for {app_name}: {exc}")
        return _fallback_web_info(app_name, str(exc))

    if not results:
        print(f"[!] No web search results found for {app_name}.")
        return _fallback_web_info(app_name)

    extracted_info = ""
    for result in results:
        title = result.get("title", "Unknown title")
        body = result.get("body", "No description provided.")
        extracted_info += f"- Title: {title}\n"
        extracted_info += f"  Info: {body}\n\n"

    print(f"Extracted Web Info:\n{extracted_info}")
    return extracted_info
