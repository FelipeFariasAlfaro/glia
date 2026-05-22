import os
import asyncio
import json
from pathlib import Path
from contextlib import AsyncExitStack
from typing import Dict, Any, Optional

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from google import genai
from google.genai import types

# Load environment variables (.env)
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

class RapidAgent:
    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.exit_stack = AsyncExitStack()
        
        # Initialize Gemini client (uses GEMINI_API_KEY env var by default)
        self.ai = genai.Client()
        self.model_name = "gemini-3.1-flash-lite-preview"

    async def connect_servers(self, config_filename: str = 'mcp_config.json'):
        """Connects to all MCP servers defined in mcp_config.json"""
        # Resolve mcp_config.json path relative to this script
        config_path = Path(__file__).parent / config_filename
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, 'r') as f:
            config = json.load(f)

        for name, server_config in config.get('mcpServers', {}).items():
            print(f"🔌 Connecting to MCP server: {name}...")
            
            # Ensure local env (API keys) is passed to subprocesses
            env = os.environ.copy()
            if 'env' in server_config:
                env.update(server_config['env'])

            server_params = StdioServerParameters(
                command=server_config['command'],
                args=server_config['args'],
                env=env
            )

            # Use AsyncExitStack to keep processes alive
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            read, write = stdio_transport
            
            session = await self.exit_stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            
            self.sessions[name] = session
            print(f"✅ Connected to {name}.")

    async def get_all_tools(self):
        """Retrieves available tools from all connected MCP servers."""
        all_tools = []
        for name, session in self.sessions.items():
            response = await session.list_tools()
            print(f"\n🛠️  Tools from {name}:")
            for tool in response.tools:
                print(f"  - {tool.name}: {tool.description[:60]}...")
                all_tools.append((name, tool))
        return all_tools

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict) -> Any:
        """Executes a tool on the specified MCP server."""
        if server_name not in self.sessions:
            raise ValueError(f"Server {server_name} not found.")
        
        print(f"\n⚙️ Executing {tool_name} on {server_name} with args: {arguments}")
        result = await self.sessions[server_name].call_tool(tool_name, arguments)
        return result

    async def cleanup(self):
        """Closes all connections cleanly."""
        await self.exit_stack.aclose()


async def run_hackathon_demo():
    agent = RapidAgent()
    
    try:
        # 1. Connect to servers (GLIA and GitLab)
        await agent.connect_servers()
        
        # 2. List available tools
        await agent.get_all_tools()
        
        # --- DEMO WORKFLOW: "The Pre-MR Tech Lead" ---
        print("\n" + "="*50)
        print("🎬 STARTING DEMO: CODE REVIEW (Pre-MR)")
        print("="*50)
        
        # Simulating a developer trying to commit this code:
        fake_git_diff = """
        --- a/src/services/payment.js
        +++ b/src/services/payment.js
        @@ -15,4 +15,5 @@
         function processPayment(payload) {
        +    logger.info("Starting payment: " + JSON.stringify(payload));
             stripe.charges.create(payload);
         }
        """
        print(f"\n👨‍💻 Developer tries to push this code:\n{fake_git_diff}")
        
        # Step 1: Ask GLIA for historical context about this change
        print("\n🧠 Consulting GLIA (Historical Memory)...")
        recall_args = {"query": "JSON.stringify in payment logs payload", "top_k": 3}
        
        try:
            glia_context = await agent.call_tool("glia", "glia_recall", recall_args)
            context_text = glia_context.content[0].text if glia_context.content else "No previous context found."
            print(f"📖 GLIA Response:\n{context_text}")
        except Exception as e:
            print(f"⚠️ Error calling GLIA: {e}")
            context_text = "Could not consult GLIA."

        # Step 2: Use Gemini to reason about the change
        print("\n🤖 Gemini reasoning over the change and memory...")
        prompt = f"""
        You are a strict Tech Lead. Review the following code change:
        
        ```diff
        {fake_git_diff}
        ```
        
        Use the following historical context from the team's memory (provided by GLIA):
        <history>
        {context_text}
        </history>
        
        If the code violates past rules, write a stern but professional comment that we would leave on the GitLab Merge Request. If it looks good, say "Approved".
        """
        
        response = agent.ai.models.generate_content(
            model=agent.model_name,
            contents=prompt,
        )
        print(f"\n📝 Agent Decision (Gemini):\n{response.text}")
        
        # Step 3: Interact with GitLab
        # In a live demo, we would call agent.call_tool("gitlab", "create_merge_request_note", {...}) here
        print("\n🚀 (Simulated) GitLab Action: The agent blocks or comments on the MR using the GitLab MCP.")

    finally:
        await agent.cleanup()

if __name__ == "__main__":
    asyncio.run(run_hackathon_demo())
