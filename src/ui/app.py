"""Gradio chat interface for the music store support assistant."""

import gradio as gr
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from src.graph.builder import build_graph
from src.ui import chat
from src.utils.logger import get_logger

logger = get_logger(__name__)

TITLE = "Music Store Support"


def start_session():
    """A fresh conversation: new thread ID, a greeting, an idle status line."""
    return chat.new_thread_id(), [{"role": "assistant", "content": chat.GREETING}], chat.status_idle()


def make_respond(graph):
    """The send handler: a generator, so the UI updates in stages instead of all at once."""

    def respond(message, history, thread_id):
        message = (message or "").strip()
        if not message:
            yield history, gr.update(), chat.status_idle(), gr.update(), gr.update()
            return

        thread_id = thread_id or chat.new_thread_id()  # safety net; demo.load normally sets it
        # Show the customer's message right away, before any model call.
        history = history + [{"role": "user", "content": message}]
        yield history, "", chat.status_processing(), gr.update(interactive=False), thread_id

        try:
            for kind, value in chat.stream_turn(graph, thread_id, message):
                if kind == "progress":
                    yield history, "", value, gr.update(interactive=False), thread_id
                else:
                    history = history + [{"role": "assistant", "content": value.reply}]
                    status = chat.status_waiting() if value.waiting else chat.status_success(value.seconds)
                    yield history, "", status, gr.update(interactive=True), thread_id
        except Exception:
            logger.exception("Turn failed")
            history = history + [{"role": "assistant", "content": chat.ERROR_REPLY}]
            yield history, "", chat.status_error(), gr.update(interactive=True), thread_id

    return respond


def build_ui(graph=None) -> gr.Blocks:
    """Build the chat UI. One shared graph serves every browser session; each session
    has its own thread ID, so the checkpointer keeps their conversations apart."""
    graph = graph or build_graph(MemorySaver(), InMemoryStore())
    respond = make_respond(graph)

    with gr.Blocks(title=TITLE, analytics_enabled=False) as demo:
        gr.Markdown(f"# {TITLE}\nAsk about our music catalog or your own invoices.")
        thread_id = gr.State()  # set per browser session in demo.load, never shared
        chatbot = gr.Chatbot(label="Conversation", height=480)
        status = gr.Markdown(chat.status_idle())
        with gr.Row():
            box = gr.Textbox(
                placeholder="Type your message and press Enter",
                show_label=False, scale=8, autofocus=True,
            )
            send = gr.Button("Send", variant="primary", scale=1)
        new = gr.Button("New Conversation")

        outputs = [chatbot, box, status, send, thread_id]
        box.submit(respond, [box, chatbot, thread_id], outputs)
        send.click(respond, [box, chatbot, thread_id], outputs)
        new.click(start_session, None, [thread_id, chatbot, status])
        demo.load(start_session, None, [thread_id, chatbot, status])

    demo.queue(default_concurrency_limit=8)
    return demo
