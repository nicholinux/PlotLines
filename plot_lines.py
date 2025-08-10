import requests
import networkx as nx
import matplotlib.pyplot as plt
from collections import defaultdict
import time
from sentence_transformers import SentenceTransformer, util

# Load embedding model
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# Broad, reusable theme vocabulary (concise, portable)
good_themes = [
    # relationships / emotion
    "love", "unrequited love", "marriage and courtship", "friendship", "betrayal",
    "jealousy", "grief", "loneliness", "nostalgia", "identity", "self-discovery",
    "alienation", "belonging", "forgiveness", "trauma", "healing", "obsession",
    "hope", "despair", "guilt", "shame", "duty", "honor",
    # society / class / power
    "social class", "wealth and poverty", "money and greed", "inheritance",
    "ambition", "power and corruption", "gender roles", "patriarchy", "morality and hypocrisy",
    # age / growth
    "coming of age", "midlife crisis", "loss of innocence",
    # conflict / law / crime
    "crime and punishment", "war", "political intrigue", "revolution",
    # truth / mind
    "unreliable narrator", "memory", "secrets", "madness", "dreams",
    "fate vs free will", "reason vs passion",
    # genre modes
    "magical realism", "surrealism", "gothic", "satire", "dystopia", "utopia",
    # art / work
    "art", "music", "science", "workplace", "servitude", "domestic service",
    # setting / place / era (portable phrasing)
    "regency-era england", "victorian england", "edwardian england",
    "pre ww2 england", "postwar japan", "meiji japan", "interwar europe",
    "rural life", "country house", "city life",
    # family
    "family", "siblings", "family conflict", "parenthood",
    # life / death
    "death", "mortality", "illness", "mourning",
]
good_theme_embeddings = embedding_model.encode(good_themes, convert_to_tensor=True)


# Blocklist of overly broad subjects
blocklist = {"fiction", "literature", "novel", "story", "books and reading", "english fiction", "american fiction"}

def get_book_data_from_isbn(isbn, country_keywords):
    """
    Look up a book by ISBN on Open Library and derive up to 5 usable tags.

    Returns:
        title (str)                         - Clean title of the input book
        final_tags (list[str], len<=5)      - Up to five tags (prioritize semantically on-theme + country/era)
        original_title_lower (str)          - Lowercased title for exclusion checks
        is_fiction (bool)                   - Heuristic from subject strings
    """
    base = "https://openlibrary.org"

    # --- Fetch edition by ISBN ---
    try:
        r = requests.get(f"{base}/isbn/{isbn}.json", timeout=20)
    except Exception:
        print("Network error while fetching ISBN.")
        return None, [], "", False
    if r.status_code != 200:
        print("ISBN not found.")
        return None, [], "", False

    book_data = r.json()
    title = (book_data.get("title") or f"Unknown Title ({isbn})").strip()

    # --- Resolve to work key ---
    works = book_data.get("works", [])
    if not works:
        return title, [], title.lower(), False
    work_key = works[0].get("key")
    if not work_key:
        return title, [], title.lower(), False

    # --- Fetch work (subjects live here) ---
    try:
        wr = requests.get(f"{base}{work_key}.json", timeout=20)
    except Exception:
        print("Network error while fetching work record.")
        return title, [], title.lower(), False
    if wr.status_code != 200:
        return title, [], title.lower(), False

    work_data = wr.json()
    raw_subjects = work_data.get("subjects", []) or []

    # --- Collect country/era/place flavored tags (we ensure these get a chance) ---
    country_tags = []
    for tag in raw_subjects:
        tag_lower = tag.lower().strip()
        if any(country.lower() in tag_lower for country in country_keywords):
            country_tags.append(tag)

    # --- Semantic filter against the expanded theme bank ---
    # Accept a subject if its max similarity to any good theme >= 0.50
    filtered_subjects = []
    similarity_threshold = 0.50
    for tag in raw_subjects:
        tag_lower = tag.lower().strip()

        # Skip obvious junk up front
        if tag_lower in blocklist:
            continue

        try:
            tag_emb = embedding_model.encode(tag, convert_to_tensor=True)
            scores = util.cos_sim(tag_emb, good_theme_embeddings)
            max_sim = scores.max().item()
        except Exception:
            # If encoding fails for any reason, skip semantic test for this tag
            max_sim = 0.0

        if max_sim >= similarity_threshold:
            filtered_subjects.append(tag)

    # --- Build final tag list with backfill to reach up to 5 ---
    # Start with semantically accepted + country/era (dedup, preserve order)
    final_tags = []
    seen = set()
    for t in filtered_subjects + country_tags:
        tl = t.lower().strip()
        if tl not in seen:
            final_tags.append(t)
            seen.add(tl)
        if len(final_tags) >= 5:
            break

    # Backfill with remaining non-blocklisted raw subjects if needed
    if len(final_tags) < 5:
        for t in raw_subjects:
            tl = t.lower().strip()
            if tl in seen or tl in blocklist:
                continue
            final_tags.append(t)
            seen.add(tl)
            if len(final_tags) >= 5:
                break

    # As a last resort, allow any leftover raw subjects (even if blocklisted) to avoid an empty graph
    if len(final_tags) < 5:
        for t in raw_subjects:
            tl = t.lower().strip()
            if tl in seen:
                continue
            final_tags.append(t)
            seen.add(tl)
            if len(final_tags) >= 5:
                break

    # --- Fiction heuristic ---
    subject_str = " ".join(raw_subjects).lower()
    is_fiction = ("fiction" in subject_str) and ("nonfiction" not in subject_str)

    return title, final_tags[:5], title.lower(), is_fiction



def find_books_by_subject(subject, original_title_lower, is_fiction_input, max_books=3):
    results = []
    seen_titles = set()

    # 1) Try subject search (precise if OL knows the subject)
    base = "https://openlibrary.org/search.json"
    urls = [
        f"{base}?subject={subject.replace(' ', '%20')}&limit={max_books + 12}",
        f"{base}?q={subject.replace(' ', '%20')}&limit={max_books + 12}",
    ]

    for query in urls:
        try:
            response = requests.get(query, timeout=20)
            if response.status_code != 200:
                continue
            data = response.json()
        except Exception:
            continue

        for doc in data.get("docs", []):
            title = (doc.get("title") or "").strip()
            if not title:
                continue

            tl = title.lower()
            if tl == original_title_lower:
                continue
            if tl in seen_titles:
                continue

            author = (doc.get("author_name") or ["Unknown"])[0]
            edition_count = doc.get("edition_count", 0)
            subject_list = " ".join(doc.get("subject", [])).lower() if "subject" in doc else ""

            # Loosen this a bit: many good works have 1 recorded edition in OL
            if edition_count < 1:
                continue

            # Soft fiction alignment: only enforce when we have subject data
            if subject_list:
                if is_fiction_input and ("fiction" not in subject_list and "novel" not in subject_list):
                    continue
                if (not is_fiction_input) and "fiction" in subject_list:
                    continue

            results.append(f"{title} by {author}")
            seen_titles.add(tl)
            if len(results) >= max_books:
                break

        if len(results) >= max_books:
            break

        time.sleep(0.3)

    return results[:max_books]



# ---------- Build Graph from ISBN ----------
def build_similarity_graph(isbn):
    country_keywords = [
        "Japan", "Canada", "United States", "England", "France",
        "Germany", "China", "India", "Mexico", "Italy", "Russia", "Korea"
    ]
    main_title, main_tags, original_title_lower, is_fiction = get_book_data_from_isbn(isbn, country_keywords)
    if not main_title:
        return None, ""

    G = nx.Graph()
    G.add_node(main_title, type="book")

    for tag in main_tags:
        G.add_node(tag, type="theme")
        G.add_edge(main_title, tag)

    seen_books = set()
    seen_books.add(main_title)

    for tag in main_tags:
        related_books = find_books_by_subject(tag, original_title_lower, is_fiction)
        time.sleep(0.5)  # Be kind to the API

        for book in related_books:
            if book not in seen_books:
                G.add_node(book, type="book")
                G.add_edge(book, tag)
                seen_books.add(book)

    return G, main_title

# ---------- Draw the Graph ----------
def draw_graph(G, center_title):
    node_colors = ["skyblue" if G.nodes[n]["type"] == "book" else "lightgreen" for n in G.nodes()]
    node_sizes = [900 if n == center_title else 700 if G.nodes[n]["type"] == "book" else 500 for n in G.nodes()]
    
    plt.figure(figsize=(14, 10))
    pos = nx.spring_layout(G, seed=42)
    nx.draw(G, pos, with_labels=True, node_color=node_colors, node_size=node_sizes,
            edge_color="gray", font_size=9)
    plt.title(f"Thematic Similarity Network: {center_title}")
    plt.axis("off")
    plt.show()
# ---------- Main ----------
if __name__ == "__main__":
    isbn = input("Enter an ISBN (e.g., 9780143124870): ").strip()
    graph, center = build_similarity_graph(isbn)
    if graph:
        draw_graph(graph, center)
    else:
        print("Could not build graph. Please check the ISBN and try again.")
