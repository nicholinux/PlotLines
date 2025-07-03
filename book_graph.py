import requests
import networkx as nx
import matplotlib.pyplot as plt
from collections import defaultdict
import time

# ---------- Determine if Tag is Useful ----------
def is_useful_tag(tag, country_keywords):
    general_tags = {"Fiction", "Literary fiction", "Accessible book", "Protected DAISY", "In library"}
    tag_lower = tag.lower()
    if tag in general_tags:
        return False
    if any(country.lower() in tag_lower for country in country_keywords):
        return True
    return True if tag not in general_tags else False

# ---------- Get Main Book Info from ISBN ----------
def get_book_data_from_isbn(isbn, country_keywords):
    url = f"https://openlibrary.org/isbn/{isbn}.json"
    response = requests.get(url)
    if response.status_code != 200:
        print("ISBN not found.")
        return None, []

    book_data = response.json()
    title = book_data.get("title", f"Unknown Title ({isbn})")

    works = book_data.get("works", [])
    if not works:
        return title, []

    work_key = works[0].get("key")
    work_url = f"https://openlibrary.org{work_key}.json"
    work_response = requests.get(work_url)
    if work_response.status_code != 200:
        return title, []

    work_data = work_response.json()
    raw_subjects = work_data.get("subjects", [])
    filtered_subjects = [tag for tag in raw_subjects if is_useful_tag(tag, country_keywords)]

    # Ensure at least one country tag is included
    country_tags = [tag for tag in raw_subjects if any(c.lower() in tag.lower() for c in country_keywords)]
    for tag in country_tags:
        if tag not in filtered_subjects:
            filtered_subjects.append(tag)

    return title, filtered_subjects[:6]  # Limit to 6 to reduce API load

# ---------- Search Open Library for Books by Subject ----------
def find_books_by_subject(subject, max_books=3):
    results = []
    query = f"https://openlibrary.org/search.json?subject={subject.replace(' ', '%20')}&limit={max_books}"
    response = requests.get(query)
    if response.status_code != 200:
        return results

    data = response.json()
    for doc in data.get("docs", []):
        title = doc.get("title")
        author = doc.get("author_name", ["Unknown"])[0]
        if title:
            results.append(f"{title} by {author}")
    return results

# ---------- Build Graph from ISBN ----------
def build_similarity_graph(isbn):
    country_keywords = ["Japan", "Canada", "United States", "England", "France", "Germany", "China", "India"]
    main_title, main_tags = get_book_data_from_isbn(isbn, country_keywords)
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
        related_books = find_books_by_subject(tag)
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
