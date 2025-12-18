from django.shortcuts import render, redirect
from ..forms import BookForm
from ..ApiManager import *
from store.repositories.BookRepo import BookRepo
from store.repositories.GenreRepo import GenreRepo
from store.repositories.PublisherRepo import PublisherRepo
import pandas as pd
import plotly.express as px
from store.repositories.StatsRepo import StatsRepo
from django.core.paginator import Paginator
from django.http import JsonResponse


book_repo = BookRepo()
genre_repo = GenreRepo()
publisher_repo = PublisherRepo()


def book_list(request):
    try:
        books = book_api.get_all_books()
        genres = genre_api.get_all_genres()
        paginator = Paginator(books, 8)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)
        context = {
            "page_obj": page_obj,
            "books": page_obj.object_list,
            "genres": genres,
            "current_genre": None
        }
        return render(request, "catalog/list.html", context)

    except Exception as ex:
        print("Помилка API:", ex)
        return render(request, "errors/500.html", status=500)


def book_list_by_genre(request, genre_id):
    try:
        current_genre = genre_api.get_by_id(genre_id)
        if not current_genre:
            return render(request, "errors/404.html", status=404)
        books = book_api.get_books_by_genre(genre_id)

        paginator = Paginator(books, 8)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        genres = genre_api.get_all_genres()
        return render(request, 'catalog/list.html', {
            'books': page_obj.object_list,
            'page_obj': page_obj,
            'genres': genres,
            'current_genre': current_genre
        })
    except Exception as ex:
        print("Помилка API:", ex)
        return render(request, "errors/500.html", status=500)


def book_list_by_publisher(request, publisher_id):
    try:
        current_publisher = publisher_api.get_by_id(publisher_id)

        if not current_publisher:
            return render(request, "errors/404.html", status=404)

        books = book_api.get_books_by_publisher(publisher_id)

        paginator = Paginator(books, 8)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        publishers = publisher_api.get_all_publishers()

        return render(request, 'catalog/list.html', {
            'books': page_obj.object_list,
            'page_obj': page_obj,
            'publishers': publishers,
            'current_publisher': current_publisher
        })
    except Exception as ex:
        print("Помилка API:", ex)
        return render(request, "errors/500.html", status=500)


def get_book_stats():
    stats = {
        "overall": {},
        "genres": [],
        "publishers": [],
    }

    overall = book_api.client.get("catalog/books/stats/overall/")
    if isinstance(overall, dict) and not overall.get("error"):
        stats["overall"] = overall
    else:
        stats["overall"] = {"avg_price": 0, "total_books": 0}

    genres = genre_api.client.get("catalog/genres/stats/")
    if isinstance(genres, list):
        stats["genres"] = genres

    publishers = publisher_api.client.get("catalog/publishers/stats/")
    if isinstance(publishers, list):
        stats["publishers"] = publishers
    return stats


def book_stats(request):
    try:
        stats = get_book_stats()
        try:
            books = book_api.get_all_books()
        except Exception as ex_books:
            print("Помилка завантаження books через API:", ex_books)
            books = []

        return render(request, "catalog/stats.html", {
            "stats": stats,
            "books": books,
        })
    except Exception as ex:
        print("Помилка stats:", ex)
        return render(request, "errors/500.html", status=500)


def book_detail(request, book_id):
    try:
        book = None
        try:
            book = book_api.get_by_id_with_related(book_id)
        except Exception as ex_book:
            print("Помилка завантаження book через API:", ex_book)
        if not book:
            return render(request, "errors/404.html", status=404)

        stats = get_book_stats()
        return render(request, "catalog/detail.html", {
            "book": book,
            "stats": stats,
        })
    except Exception as ex:
        print("Помилка detail:", ex)
        return render(request, "errors/400.html", status=400)


def book_update(request, book_id):
    try:
        book = book_repo.get_by_id(book_id)
        if not book:
            return render(request, "errors/404.html", status=404)

        if request.method == "POST":
            form = BookForm(request.POST, request.FILES, instance=book)
            if form.is_valid():
                form.save()
                return redirect("catalog:book_detail", book_id=book_id)
            return render(request, "errors/400.html", status=400)
        form = BookForm(instance=book)
        return render(request, "catalog/form.html", {"form": form})
    except Exception as ex:
        print("Помилка update:", ex)
        return render(request, "errors/500.html", status=500)


def book_create(request):
    response = None
    try:
        if request.method == "POST":
            form = BookForm(request.POST, request.FILES)
            if form.is_valid():
                data = form.cleaned_data

                data['authors'] = [a.author_id for a in data.pop('author', [])]
                data['genres'] = [g.genre_id for g in data.pop('genres', [])]
                data['publisher'] = data['publisher'].publisher_id

                image_file = request.FILES.get("image")
                response = book_api.create(
                    data=data,
                    image_file=image_file
                )
                print("API create response:", response)
                if response and response.get("book_id"):
                    return redirect("catalog:book_list")
                else:
                    return render(request, "errors/400.html", {"response": response}, status=400)

        form = BookForm()
        return render(request, "catalog/form.html", {"form": form})
    except Exception as ex:
        print("Помилка create:", ex)
        return render(request, "errors/500.html", status=500)


def book_delete(request, book_id):
    try:
        book = book_api.get_by_id(book_id)
        if not book:
            return render(request, "errors/404.html", status=404)
        if request.method != "POST":
            return render(request, "catalog/delete.html", {"book": book})
        ok = book_api.delete(book_id=book_id)
        if ok:
            return redirect("catalog:book_list")
    except Exception as ex:
        print("Помилка API:", ex)
        return render(request, "errors/500.html", status=500)


def avg_price_by_genre_store(request):
    genre = request.GET.get("genre", "")
    data_queryset = list(StatsRepo.avg_price_by_genre_and_store())
    df = pd.DataFrame(data_queryset)

    available_genres = df['genre_name'].unique(
    ).tolist() if not df.empty else []

    if not genre and available_genres:
        genre = available_genres[0]
    if genre and genre in available_genres:
        filtered_df = df[df['genre_name'] == genre]
    else:
        filtered_df = pd.DataFrame()

    if not filtered_df.empty:
        filtered_df = filtered_df.sort_values('avg_price', ascending=False)
        fig = px.line(
            filtered_df,
            x='store_name',
            y='avg_price',
            markers=True,
            labels={'store_name': 'Магазин', 'avg_price': 'Середня ціна, грн'},
            template='plotly_white'
        )
        fig.update_layout(
            xaxis={'categoryorder': 'total descending', 'tickangle': 20},
            yaxis={'rangemode': 'tozero'}
        )
        fig.update_traces(line_color='#f4a259')

        graph_json = fig.to_json()
    else:
        graph_json = "{}"

    return JsonResponse({
        'graph_json': graph_json,
        'available_genres': available_genres,
        'current_genre': genre
    })


def error_404(request, exception):
    return render(request, "errors/404.html", status=404)


def error_500(request):
    return render(request, "errors/500.html", status=500)


def error_403(request, exception):
    return render(request, "errors/403.html", status=403)


def error_400(request, exception):
    return render(request, "errors/400.html", status=400)
