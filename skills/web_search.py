import urllib.parse
import webbrowser
import logging

logger = logging.getLogger(__name__)

class WebSearchSkill:
    """
    Skill for searching the web and opening default browser.
    """
    @staticmethod
    def search(query: str) -> str:
        """
        Launches Google search in default browser for given query.
        """
        clean_query = query.strip()
        if not clean_query:
            return "What would you like me to search for?"

        encoded_query = urllib.parse.quote_plus(clean_query)
        url = f"https://www.google.com/search?q={encoded_query}"
        
        logger.info(f"Opening browser for web search query: '{clean_query}'")
        try:
            webbrowser.open(url)
            return f"Searching Google for {clean_query}"
        except Exception as e:
            logger.error(f"Failed to launch browser: {e}")
            return f"Failed to perform search for {clean_query}"
