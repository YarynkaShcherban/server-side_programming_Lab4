from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Count, Avg
import requests
from django.http import (
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseServerError,
)
from store.models import Book, Author, Genre, Publisher
from .forms import BookForm
from .ApiManager import *
from store.repositories.BookRepo import BookRepo
from store.repositories.GenreRepo import GenreRepo
from store.repositories.PublisherRepo import PublisherRepo
import pandas as pd
from plotly.offline import plot
import plotly.express as px
from store.repositories.StatsRepo import StatsRepo


book_repo = BookRepo()
genre_repo = GenreRepo()
publisher_repo = PublisherRepo()


def book_list(request):
    try:
        books = book_api.get_all_books()
        genres = genre_api.get_all_genres()

        context = {
            "books": books,
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
        genres = genre_api.get_all_genres()
        return render(request, 'catalog/list.html', {
            'books': books,
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
        publishers = publisher_api.get_all_publishers()

        return render(request, 'catalog/list.html', {
            'books': books,
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

                if response.get("book_id"):
                    return redirect("catalog:book_list")

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


def get_dashboard_figures():

    template_style = 'plotly_white'

    line_chart_layout_updates = {
        'xaxis': {
            'gridcolor': '#e0e0e0', 'griddash': 'dash'
        },
        'yaxis': {
            'gridcolor': '#e0e0e0', 'griddash': 'dash'
        },
        'plot_bgcolor': 'white'
    }
    # --- 1. Статистика по жанрах ---
    genres_data = list(StatsRepo.genres_with_books_and_avg_price())
    genres_df = pd.DataFrame(genres_data, columns=[
                             'name', 'num_books', 'avg_price'] if genres_data else [])

    fig_genres_count, fig_genres_price = None, None
    if not genres_df.empty:
        # Графік 1: Кількість книг по жанрах (сортування за кількістю)
        genres_count_df = genres_df.sort_values('num_books', ascending=False)
        fig_genres_count = px.bar(genres_count_df, x='name', y='num_books',
                                  title="Кількість книг по жанрах",
                                  labels={'name': 'Жанр',
                                          'num_books': 'Кількість книг'},
                                  template=template_style)
        fig_genres_count.update_traces(marker_color='#8ECAE6')

        # Графік 2: Середня ціна книг по жанрах (сортування за ціною)
        genres_price_df = genres_df.sort_values('avg_price', ascending=False)
        fig_genres_price = px.line(genres_price_df, x='name', y='avg_price',
                                   title="Середня ціна книг по жанрах",
                                   labels={'name': 'Жанр',
                                           'avg_price': 'Середня ціна, грн'},
                                   template=template_style, markers=True)
        fig_genres_price.update_layout(line_chart_layout_updates)
    # --- 2. Статистика по авторах ---
    authors_data = list(StatsRepo.authors_avg_book_price())
    authors_df = pd.DataFrame(authors_data, columns=[
                              'first_name', 'last_name', 'avg_price'] if authors_data else [])

    fig_authors_price = None
    if not authors_df.empty:
        # Графік 3: Середня ціна книг по авторах (сортування за ціною)
        authors_price_df = authors_df.sort_values('avg_price', ascending=False)
        authors_price_df['full_name'] = authors_price_df['first_name'] + \
            ' ' + authors_price_df['last_name']
        fig_authors_price = px.bar(authors_price_df, x='full_name', y='avg_price',
                                   title="Середня ціна книг по авторах",
                                   labels={'full_name': 'Автор',
                                           'avg_price': 'Середня ціна, грн'},
                                   template=template_style,
                                   hover_data={'avg_price': ':.2f'})
    fig_authors_price.update_traces(marker_color='#e9c46a')

    top_authors_data = list(StatsRepo.top_authors_by_book_count())
    top_authors_df = pd.DataFrame(top_authors_data, columns=[
                                  'first_name', 'last_name', 'num_books'] if top_authors_data else [])
    custom_colors = ['#22577a', '#38a3a5', '#57cc99', '#80ed99', '#c7f9cc']
    fig_top_authors = None
    if not top_authors_df.empty:
        # Графік 4: Топ авторів за кількістю книг
        top_authors_df['full_name'] = top_authors_df['first_name'] + \
            ' ' + top_authors_df['last_name']
        fig_top_authors = px.pie(top_authors_df,
                                 values='num_books',
                                 names='full_name',
                                 title=f"Топ {len(top_authors_df)} авторів за кількістю книг",
                                 template=template_style,
                                 color_discrete_sequence=custom_colors[:len(
                                     top_authors_df)],
                                 hole=0.3)

    # --- 3. Статистика по видавництвах ---
    publishers_data = list(StatsRepo.publishers_avg_price())
    publishers_df = pd.DataFrame(publishers_data, columns=[
                                 'name', 'num_books', 'avg_price'] if publishers_data else [])

    fig_publishers_price, fig_expensive_pub = None, None
    if not publishers_df.empty:
        # Графік 5: Середня ціна книг по видавництвах (сортування за ціною)
        publishers_price_df = publishers_df.sort_values(
            'avg_price', ascending=False)
        fig_publishers_price = px.bar(publishers_price_df, x='name', y='avg_price',
                                      title="Середня ціна книг по видавництвах",
                                      labels={'name': 'Видавництво',
                                              'avg_price': 'Середня ціна, грн'},
                                      template=template_style,
                                      hover_data={'avg_price': ':.2f'})
        fig_publishers_price.update_traces(marker_color='#2a9d8f')

    expensive_pub_data = list(StatsRepo.expensive_publishers())
    expensive_pub_df = pd.DataFrame(expensive_pub_data, columns=[
                                    'name', 'avg_price'] if expensive_pub_data else [])

    if not expensive_pub_df.empty:
        # Графік 6: Дорогі видавництва (використовуємо порог з StatsRepo)

        fig_expensive_pub = px.pie(expensive_pub_df, names='name', values='avg_price',
                                   title="Дорогі видавництва (розподіл за середньою ціною)",
                                   template=template_style,
                                   hole=0.3)  # Створюємо пончик-графік

    # --- 4. Статистика продажів по магазинах ---
    stores_data = list(StatsRepo.store_sales_stats())
    stores_df = pd.DataFrame(stores_data, columns=[
                             'name', 'total_sales', 'total_purchases'] if stores_data else [])

    fig_store_sales, fig_store_count = None, None
    if not stores_df.empty:
        # Графік 7: Сума продажів по магазинах (сортування за сумою)
        stores_sales_df = stores_df.sort_values('total_sales', ascending=False)
        fig_store_sales = px.bar(stores_sales_df, x='name', y='total_sales',
                                 title="Сума продажів по магазинах",
                                 labels={'name': 'Магазин',
                                         'total_sales': 'Сума продажів, грн'},
                                 template=template_style,
                                 color='total_sales',
                                 color_continuous_scale=px.colors.sequential.Viridis)

        # Графік 8: Кількість продажів по магазинах (сортування за кількістю)
        stores_count_df = stores_df.sort_values(
            'total_purchases', ascending=False)
        fig_store_count = px.bar(stores_count_df, x='name', y='total_purchases',
                                 title="Кількість продажів по магазинах",
                                 labels={'name': 'Магазин',
                                         'total_purchases': 'Кількість продажів'},
                                 template=template_style,
                                 color='total_purchases',
                                 color_continuous_scale=px.colors.sequential.Cividis)

    return {
        'fig_genres_count': plot(fig_genres_count, output_type='div') if fig_genres_count else "<p>Немає даних</p>",
        'fig_genres_price': plot(fig_genres_price, output_type='div') if fig_genres_price else "<p>Немає даних</p>",
        'fig_authors_price': plot(fig_authors_price, output_type='div') if fig_authors_price else "<p>Немає даних</p>",
        'fig_top_authors': plot(fig_top_authors, output_type='div') if fig_top_authors else "<p>Немає даних</p>",
        'fig_publishers_price': plot(fig_publishers_price, output_type='div') if fig_publishers_price else "<p>Немає даних</p>",
        'fig_expensive_pub': plot(fig_expensive_pub, output_type='div') if fig_expensive_pub else "<p>Немає даних</p>",
        'fig_store_sales': plot(fig_store_sales, output_type='div') if fig_store_sales else "<p>Немає даних</p>",
        'fig_store_count': plot(fig_store_count, output_type='div') if fig_store_count else "<p>Немає даних</p>",
    }


def dashboard_page(request):
    try:
        context = get_dashboard_figures()
        return render(request, 'catalog/dashboard.html', context)
    except Exception as e:
        print(e)
        return render(request, 'catalog/error.html', status=500)


@api_view(['GET'])
def dashboard_view(request):
    figures = get_dashboard_figures()
    return Response(figures)


@api_view(['GET'])
def genres_stats_api(request):
    return Response(list(StatsRepo.genres_with_books_and_avg_price()))


@api_view(['GET'])
def authors_avg_price_api(request):
    return Response(list(StatsRepo.authors_avg_book_price()))


@api_view(['GET'])
def publishers_stats_api(request):
    return Response(list(StatsRepo.publishers_avg_price()))


@api_view(['GET'])
def top_authors_api(request):
    return Response(list(StatsRepo.top_authors_by_book_count()))


@api_view(['GET'])
def expensive_publishers_api(request):
    return Response(list(StatsRepo.expensive_publishers()))


@api_view(['GET'])
def store_sales_api(request):
    return Response(list(StatsRepo.store_sales_stats()))


def error_404(request, exception):
    return render(request, "errors/404.html", status=404)


def error_500(request):
    return render(request, "errors/500.html", status=500)


def error_403(request, exception):
    return render(request, "errors/403.html", status=403)


def error_400(request, exception):
    return render(request, "errors/400.html", status=400)
