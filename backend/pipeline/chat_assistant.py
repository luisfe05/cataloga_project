"""Chat assistant."""

import json
import os
import re
import unicodedata

from backend.models.document import MEDIA_TYPES
from backend.pipeline import assistant_guard, folder_tree, naming
from backend.pipeline.naming import clean_new_name

MAX_CONTEXT_DOCUMENTS = 30

MAX_HISTORY = 6
MAX_HISTORY_CHARS = 500

MAX_MESSAGE_CHARS = assistant_guard.MAX_MESSAGE_CHARS
MAX_REPLY_CHARS = 2000
MAX_FILTER_TEXT = 100

MAX_LISTED = 10

STATUSES = ("Classified", "Manual Review")

# Words that match almost every document. Words under 3 letters too.
STOP_WORDS = {
    "the", "and", "for", "with", "from", "about", "find", "show", "all",
    "file", "files", "rename", "this", "that", "what", "which", "please",
    "los", "las", "del", "con", "para", "por", "que", "una", "uno",
    "este", "esta", "busca", "buscar", "muestra", "archivo", "archivos",
    "renombra", "renombrar", "sobre", "cual", "cuales",
}

# The six rules come first, the same ones every pipeline prompt has.
SYSTEM_PROMPT = assistant_guard.MODEL_RULES + """
You are Ask Cataloga, the assistant inside Cataloga,
a desktop app that catalogs the files of one research project.

You never do anything yourself: you answer with ONE JSON object and
nothing else. Every answer has these fields:
- "in_scope": true when the message is about the project's files, the
  catalog, or how to use Cataloga; false for anything else.
- "category": "files" (about the files or the catalog), "help" (a
  greeting, or how to use Cataloga), or "other" (out of scope).
- "action": one action from the list below.
- "answer": your text, one to three sentences, in the user's language.
- "sources": the ids of the documents you used. A "files" answer must
  cite at least one id from "documents".

When "in_scope" is false, use the action "answer" and leave "answer"
empty: Cataloga shows its own message.

Actions:
1. {"action": "answer"}
   Plain text in "answer".
2. {"action": "show_documents", "document_ids": [ids]}
   Show some documents as cards. Use this also for questions about
   dates.
3. {"action": "filter_catalog", "filters": {
    "media_type": "Press|Documents|Photos|Audio|Video",
    "source": "...", "status": "Classified|Manual Review",
    "text": "..."}}
   Open the catalog with filters. Leave out any filter you do not need.
   There is no date filter. For a search by keyword, use "text".
4. {"action": "summarize_project"}
   Describe the project using the numbers in "project".
5. {"action": "propose_rename", "document_id": id, "new_name": "..."}
   Propose a new name for ONE document. The user must confirm it, so
   never say the file was renamed. Do not include the extension.

Facts:
- Use only document ids from "documents". Never invent ids, names,
  dates or numbers.
- You cannot delete or move files, and you cannot read the full content
  of a file: only its name, type, date, source, summary, keywords,
  category, subcategory and counterparty.
"""

# Added to SYSTEM_PROMPT only in projects with their own folder tree.
MOVE_PROMPT = """
This project files documents in its own folders ("folders"), so there
is one more action:
6. {"action": "propose_move", "document_id": id, "folder": "..."}
   Propose moving ONE document to another folder. "folder" is one entry
   of "folders", exactly as written. The user must confirm it, so never
   say the file was moved.
"""

# Categories the model may answer with; "help" needs no sources.
CATEGORIES = ("files", "help", "other")


def fold(text):
    """Return text in lowercase and without accents, for searching."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    return text.encode("ascii", "ignore").decode("ascii").lower()


def words_in(message):
    """Return the words of a message that are worth searching for."""
    words = re.findall(r"[a-z0-9]+", fold(message))
    return {word for word in words
            if len(word) >= 3 and word not in STOP_WORDS}


def find_documents(documents, message):
    """Pick the documents most related to a message."""
    words = words_in(message)
    scored = []
    for doc in documents:
        text = fold(" ".join([doc.filename, doc.original_filename,
                              doc.source or "", doc.summary or "",
                              doc.document_date or "", doc.topic or "",
                              " ".join(doc.keywords), doc.category or "",
                              doc.subcategory or "",
                              doc.counterparty or ""]))
        score = sum(1 for word in words if word in text)
        if score:
            scored.append((score, doc))
    if not scored:
        newest = sorted(documents, key=lambda doc: doc.id, reverse=True)
        return newest[:MAX_CONTEXT_DOCUMENTS]
    # Most points first; among equals, the newest first.
    scored.sort(key=lambda pair: (-pair[0], -pair[1].id))
    return [doc for score, doc in scored[:MAX_CONTEXT_DOCUMENTS]]


def document_card(doc):
    """Return the fields the chat shows for one document."""
    return {
        "id": doc.id,
        "filename": doc.filename,
        "media_type": doc.media_type,
        "document_date": doc.document_date,
        "source": doc.source,
        "summary": doc.summary,
        "status": doc.status,
        "keywords": doc.keywords,
        "category": doc.category,
        "subcategory": doc.subcategory,
        "counterparty": doc.counterparty,
    }


def clean_history(history):
    """Keep only the last messages the frontend sent, in a safe shape."""
    if not isinstance(history, list):
        return []
    clean = []
    for item in history[-MAX_HISTORY:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        text = item.get("text")
        if role in ("user", "assistant") and isinstance(text, str):
            clean.append({"role": role, "text": text[:MAX_HISTORY_CHARS]})
    return clean


def build_prompt(message, history, summary, documents, tree=None,
                 nonce=None):
    """Build the text sent to the model: the data block, then the message.

    Everything that comes from the catalog goes between the data markers
    of this call; the user's message and the conversation stay outside.
    """
    data = {
        "project": summary,
        "documents": [document_card(doc) for doc in documents],
    }
    if tree is not None:
        data["folders"] = folder_tree.all_places(tree)
    nonce = nonce or assistant_guard.new_nonce()
    return "\n".join([
        assistant_guard.wrap_data(json.dumps(data, ensure_ascii=False),
                                  nonce),
        "Conversation so far: " + json.dumps(history, ensure_ascii=False),
        "User message: " + message[:MAX_MESSAGE_CHARS],
    ])


def parse_reply(answer):
    """Read the JSON object in the model's answer."""
    if not answer:
        return None
    start = answer.find("{")
    end = answer.rfind("}")
    if start == -1 or end < start:
        return None
    try:
        data = json.loads(answer[start:end + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def make_response(action, reply="", sources=None, notice=None):
    """Build a chat response in the shape the frontend expects."""
    return {
        "action": action,
        "reply": reply,
        "notice": notice,
        "sources": sources or [],
        "documents": [],
        "filters": {},
        "rename": None,
        "move": None,
        "project": None,
    }


def notice_response(code):
    """Return a plain 'answer' with a friendly message code."""
    return make_response("answer", notice=code)


def clean_reply(data):
    """Return the model's text ("answer", or the older "reply"), cut short."""
    reply = data.get("answer")
    if not isinstance(reply, str) or not reply.strip():
        reply = data.get("reply")
    if not isinstance(reply, str):
        return ""
    return reply.strip()[:MAX_REPLY_CHARS]


def valid_ids(value, context):
    """Keep only the ids that belong to a document of the project."""
    if not isinstance(value, list):
        return []
    ids = []
    for item in value:
        # True and False count as 1 and 0 in Python; they are not ids.
        if isinstance(item, bool):
            continue
        try:
            doc_id = int(item)
        except (TypeError, ValueError):
            continue
        if doc_id in context["documents"] and doc_id not in ids:
            ids.append(doc_id)
    return ids[:MAX_LISTED]


def cards_for(ids, context):
    """Return the document cards for a list of valid ids."""
    return [document_card(context["documents"][doc_id]) for doc_id in ids]


def sources_of(data, context):
    """Return the cards of the sources the model cited."""
    return cards_for(valid_ids(data.get("sources"), context), context)


def check_answer(data, context):
    """Validate the 'answer' action: plain text."""
    reply = clean_reply(data)
    if not reply:
        return notice_response("invalid_reply")
    return make_response("answer", reply, sources_of(data, context))


def check_show_documents(data, context):
    """Validate 'show_documents': a list of documents shown as cards."""
    ids = valid_ids(data.get("document_ids"), context)
    if not ids:
        return notice_response("no_documents")
    response = make_response("show_documents", clean_reply(data),
                             sources_of(data, context))
    response["documents"] = cards_for(ids, context)
    return response


def match_value(value, allowed):
    """Return the allowed value that matches, ignoring capital letters."""
    if not isinstance(value, str):
        return None
    for item in allowed:
        if fold(item) == fold(value.strip()):
            return item
    return None


def check_filter_catalog(data, context):
    """Validate 'filter_catalog': filters the Catalog screen applies."""
    sent = data.get("filters")
    if not isinstance(sent, dict):
        sent = {}
    filters = {}
    media_type = match_value(sent.get("media_type"), MEDIA_TYPES)
    if media_type:
        filters["media_type"] = media_type
    status = match_value(sent.get("status"), STATUSES)
    if status:
        filters["status"] = status
    source = match_value(sent.get("source"), context["sources"])
    if source:
        filters["source"] = source
    text = sent.get("text")
    if isinstance(text, str) and text.strip():
        filters["text"] = text.strip()[:MAX_FILTER_TEXT]

    if not filters:
        return notice_response("no_filters")
    response = make_response("filter_catalog", clean_reply(data),
                             sources_of(data, context))
    response["filters"] = filters
    return response


def check_summarize_project(data, context):
    """Validate 'summarize_project': the model's text about the project."""
    reply = clean_reply(data)
    if not reply:
        return notice_response("invalid_reply")
    response = make_response("summarize_project", reply,
                             sources_of(data, context))
    response["project"] = context["summary"]
    return response


def check_propose_rename(data, context):
    """Validate 'propose_rename'. Nothing is renamed here."""
    ids = valid_ids([data.get("document_id")], context)
    if not ids:
        return notice_response("rename_not_found")
    doc = context["documents"][ids[0]]
    if not context.get("can_rename", True) or \
            naming.is_protected(doc.filename):
        return notice_response("rename_unavailable")
    extension = os.path.splitext(doc.filename)[1]
    new_name = clean_new_name(data.get("new_name"), extension)
    if not new_name:
        return notice_response("rename_invalid")
    if new_name == doc.filename:
        return notice_response("rename_same")

    response = make_response("propose_rename", clean_reply(data),
                             [document_card(doc)])
    response["rename"] = {
        "document_id": doc.id,
        "current_name": doc.filename,
        "new_name": new_name,
    }
    return response


def check_propose_move(data, context):
    """Validate 'propose_move'. Nothing is moved here."""
    tree = context["tree"]
    if tree is None:
        return notice_response("move_unavailable")
    ids = valid_ids([data.get("document_id")], context)
    if not ids:
        return notice_response("rename_not_found")
    doc = context["documents"][ids[0]]
    place = folder_tree.find_place(tree, data.get("folder"))
    if place is None:
        return notice_response("move_invalid")
    if doc.folder_path == place:
        return notice_response("move_same")

    response = make_response("propose_move", clean_reply(data),
                             [document_card(doc)])
    response["move"] = {
        "document_id": doc.id,
        "filename": doc.filename,
        "current_folder": doc.folder_path or "",
        "new_folder": place,
    }
    return response


# The fixed list of actions the model may choose from. Anything else the
# model answers is refused. None of them changes a file: the two
# proposals wait for the user's Confirm.
ACTIONS = {
    "answer": check_answer,
    "show_documents": check_show_documents,
    "filter_catalog": check_filter_catalog,
    "summarize_project": check_summarize_project,
    "propose_rename": check_propose_rename,
    "propose_move": check_propose_move,
}
ALLOWED_ACTIONS = tuple(ACTIONS)


def make_context(documents, summary, tree=None, can_rename=True):
    """Collect what the validators need to know about the project."""
    sources = sorted({doc.source for doc in documents if doc.source})
    return {
        "documents": {doc.id: doc for doc in documents},
        "sources": sources,
        "summary": summary,
        "tree": tree,
        "can_rename": can_rename,
    }


def in_scope(data, response):
    """Say whether the model's answer stays inside the project.

    Out of scope: "in_scope" is not true, the category is unknown, or a
    "files" answer cites no document of the project. "help" (a greeting,
    how to use Cataloga) needs no sources.
    """
    if data.get("in_scope") is not True:
        return False
    category = data.get("category")
    if category not in CATEGORIES or category == "other":
        return False
    if category == "help":
        return True
    # Cards, filters, proposals and the project summary carry their own
    # evidence, and so does a notice of the app (nothing found, a bad
    # proposal); a plain answer about the files must cite one.
    return response["action"] != "answer" or bool(response["sources"]) \
        or bool(response.get("notice"))


def run_chat(repo, client, message, history=None, throttle=None,
             project=""):
    """Answer one chat message. Reads the catalog, never changes it.

    In order: the phrase filter and the pace (before any call), the
    model, the JSON and the scope, the action from the fixed list, and
    the reply filter (after the call).
    """
    if throttle is not None:
        pace = throttle.check(project)
        if pace == "paused":
            return notice_response("paused")
        if pace == "busy":
            return notice_response("too_many")
    blocked = assistant_guard.check_user_message(message)
    if blocked:
        return block_response(blocked, throttle, project)

    documents = repo.get_all_documents()
    summary = repo.get_project_summary()
    tree = repo.get_folder_tree()
    context = make_context(documents, summary, tree,
                           can_rename=repo.can_move_files())
    nonce = assistant_guard.new_nonce()
    prompt = build_prompt(message, clean_history(history), summary,
                          find_documents(documents, message), tree, nonce)
    system_prompt = SYSTEM_PROMPT if tree is None else \
        SYSTEM_PROMPT + MOVE_PROMPT
    system_prompt += "\n" + assistant_guard.data_rule(nonce)

    answer = client.ask(system_prompt, prompt) if client else None
    if answer is None:
        return notice_response("ai_unavailable")
    data = parse_reply(answer)
    # No JSON, or a JSON that says so: out of scope, nothing is shown.
    if data is None:
        return block_response("out_of_scope", throttle, project)
    action = data.get("action")
    # A list or a dict cannot be looked up in ACTIONS.
    check = ACTIONS.get(action) if isinstance(action, str) else None
    if check is None:
        return block_response("out_of_scope", throttle, project)
    response = check(data, context)
    # The reply itself: never a key, a command or a path outside.
    held = assistant_guard.check_reply(response["reply"], project)
    if held:
        return block_response(held, throttle, project)
    if not in_scope(data, response):
        return block_response("out_of_scope", throttle, project)
    if throttle is not None:
        throttle.note_ok(project)
    return response


def block_response(category, throttle=None, project=""):
    """The fixed message of a block, logged by category only."""
    assistant_guard.log_block(category, project)
    if throttle is not None:
        throttle.note_block(project)
    notice = "out_of_scope" if category == "out_of_scope" else "blocked"
    return notice_response(notice)
