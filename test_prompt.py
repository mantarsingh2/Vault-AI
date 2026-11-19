"""Interactive CLI tool to test Vault AI LangGraph workflow."""

import sys
from core.ai.orchestration.graph import vault_graph


def run_single(query: str):
    print(f"\n{'='*60}")
    print(f"PROMPT: {query}")
    print(f"{'='*60}")
    result = vault_graph.invoke({"user_query": query})
    print(f"Status: {result.get('status')}")
    print(f"Intent: {result.get('intent')}")
    print(f"Steps:  {result.get('steps')}")
    print(f"\nResponse:\n{result.get('response')}\n")


def interactive_mode():
    print("=" * 60)
    print("Vault AI LangGraph Interactive Console")
    print("Type any prompt to test LangGraph. Type 'exit' or 'quit' to quit.")
    print("=" * 60)

    while True:
        try:
            query = input("\nVault-AI > ").strip()
            if not query:
                continue
            if query.lower() in ["exit", "quit", "q"]:
                print("Exiting.")
                break
            run_single(query)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_single(" ".join(sys.argv[1:]))
    else:
        interactive_mode()

