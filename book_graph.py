import requests
import networkx as nx
import matplotlib.pyplot as plt
from collections import defaultdict
import time

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

    general_tags = {
        "fiction", "literary fiction", "accessible book",
        "protected daisy", "in library", "large type books"
    }

    filtered_subjects = []
    country_tags = []

    for tag in raw_subjects:
        tag_lower = tag.lower()
        if any(country.lower() in tag_lower for country in country_keywords):
            country_tags.append(tag)
        elif tag_lower not in general_tags:
            filtered_subjects.append(tag)

    # Ensure at least one country tag is included
    if country_tags:
        for tag in country_tags:
            if tag not in filtered_subjects:
                filtered_subjects.append(tag)

    return title, filtered_subjects[:6]  # Limit to 6


# ---------- Search Open Library for Books by Subject ----------
def find_books_by_subject(subject, original_title_lower, max_books=3):
    results = []
    query = f"https://openlibrary.org/search.json?subject={subject.replace(' ', '%20')}&limit={max_books+2}"
    response = requests.get(query)
    if response.status_code != 200:
        return results

    data = response.json()
    for doc in data.get("docs", []):
        title = doc.get("title", "").strip()
        author = doc.get("author_name", ["Unknown"])[0]
        book_label = f"{title} by {author}"

        # Avoid suggesting the input book again
        if title.lower().strip() == original_title_lower:
            continue

        if title:
            results.append(book_label)

        if len(results) >= max_books:
            break

    return results

# ---------- Build Graph from ISBN ----------
def build_similarity_graph(isbn):
    country_keywords = [
    "Japan", "Canada", "United States", "England", "France",
    "Germany", "China", "India", "Mexico", "Italy", "Russia", "Korea"
]
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
    # ---------- Main ----------
if __name__ == "__main__":
    isbn = input("Enter an ISBN (e.g., 9780143124870): ").strip()
    graph, center = build_similarity_graph(isbn)
    if graph:
        draw_graph(graph, center)
    else:
        print("Could not build graph. Please check the ISBN and try again.")
