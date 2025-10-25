
| Category | Best Practice / Technique | Detail and Purpose |
| :--- | :--- | :--- | 
| **Job Initialization (Initial Context)** | **Pre-load user/task-specific data** | Load data into the `AgentSession`'s `ChatContext` before connecting to the room and starting the session. This is essential for tasks like loading a user's profile information from a database. | 
| **Tool Definition and Use** | **Define specific tools** | Offer the LLM a choice of tools to achieve high precision or take external actions. Tools should be as specific as needed (e.g., defining separate tools for `search_calendar`, `create_event`, `update_event`, and `delete_event`). |
| **Retrieval-Augmented Generation (RAG)** | **Use `on_user_turn_completed`** | Perform RAG lookup based on the user's most recent turn *prior* to the LLM generating a response. This method is highly performant as it avoids extra round-trips associated with standard tool calls. | 
| **Custom Models** | **Use Fine-Tuned Models** | Fine-tune models for your specific use case to achieve the most relevant results, either by exploring LLM plugins that support fine-tuning or by integrating a custom model via Ollama. | 
