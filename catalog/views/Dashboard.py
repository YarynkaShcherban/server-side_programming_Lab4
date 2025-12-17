from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Count, Avg
import requests
from django.http import (
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseServerError,
)
from store.models import Book, Author, Genre, Publisher
from ..forms import BookForm
from ..ApiManager import *
from store.repositories.BookRepo import BookRepo
from store.repositories.GenreRepo import GenreRepo
from store.repositories.PublisherRepo import PublisherRepo
import pandas as pd
from plotly.offline import plot
import plotly.express as px
from store.repositories.StatsRepo import StatsRepo
from django.core.paginator import Paginator
from django.http import JsonResponse
from store.views.benchmark_service import BenchmarkService
import time
from concurrent.futures import ThreadPoolExecutor

book_repo = BookRepo()
genre_repo = GenreRepo()
publisher_repo = PublisherRepo()

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
        # Графік 6: Дорогі видавництва (використовуємо поріг з StatsRepo)

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


def benchmark_view(request):
    try:
        df_200 = BenchmarkService.get_benchmark_data(n_requests=200)
        opt_200 = df_200.loc[df_200['total_time'].idxmin()]
        fig_200 = px.line(df_200, x='threads', y='total_time', title="Результати для 200 запитів",
                         markers=True, template='plotly_white')
        graph_200 = plot(fig_200, output_type='div')

        df_500 = BenchmarkService.get_benchmark_data(n_requests=500)
        opt_500 = df_500.loc[df_500['total_time'].idxmin()]
        fig_500 = px.line(df_500, x='threads', y='total_time', title="Результати для 500 запитів",
                         markers=True, template='plotly_white')
        fig_500.update_traces(line_color='#ef476f')
        graph_500 = plot(fig_500, output_type='div')

        df_10000 = BenchmarkService.get_benchmark_data(n_requests=10000)
        opt_10000 = df_10000.loc[df_10000['total_time'].idxmin()]
        fig_10000 = px.line(df_10000, x='threads', y='total_time', title="Навантаження: 10 000 запитів",
                           markers=True, template='plotly_white', color_discrete_sequence=['#8B5CF6'])
        graph_10000 = plot(fig_10000, output_type='div')

        def get_segment_avg(chunk_ids):
            return Book.objects.filter(book_id__in=chunk_ids).aggregate(Avg('price'))['price__avg'] or 0

        all_ids = list(Book.objects.values_list('book_id', flat=True))
        test_threads = [1, 2, 4, 8, 16, 32, 64, 128, 256] 
        async_results = []

        for n in test_threads:
            chunk_size = max(1, len(all_ids) // n)
            chunks = [all_ids[i:i + chunk_size] for i in range(0, len(all_ids), chunk_size)]
            start_time = time.time()
            with ThreadPoolExecutor(max_workers=n) as executor:
                list(executor.map(get_segment_avg, chunks))
            async_results.append({'threads': n, 'execution_time': time.time() - start_time})

        df_async = pd.DataFrame(async_results)
        idx_min = df_async['execution_time'].idxmin()
        fig_async = px.line(
            df_async, 
            x='threads', 
            y='execution_time', 
            title="Вплив кількості потоків на час обробки",
            labels={'threads': 'Кількість потоків', 'execution_time': 'Час виконання (сек)'},
            markers=True, 
            template='plotly_white'
        )
        fig_async.update_traces(line_color='#00CC96')

        return render(request, 'catalog/benchmark.html', {
            'graph_200': graph_200,
            'graph_500': graph_500,
            'graph_10000': graph_10000,
            'opt_200': {'threads': int(opt_200['threads']), 'time': round(opt_200['total_time'], 4)},
            'opt_500': {'threads': int(opt_500['threads']), 'time': round(opt_500['total_time'], 4)},
            'opt_10000': {'threads': int(opt_10000['threads']), 'time': round(opt_10000['total_time'], 4)},
            'table_200': df_200.to_dict('records'),
            'table_500': df_500.to_dict('records'),
            'table_10000': df_10000.to_dict('records'),
            'graph_div': plot(fig_async, output_type='div'),
            'table_data': df_async.to_dict('records'),
            'optimal_threads': int(df_async.loc[idx_min]['threads']),
            'min_time': round(df_async.loc[idx_min]['execution_time'], 4)
        })
    except Exception as e:
        return render(request, "errors/500.html", {"error": str(e)}, status=500)
    

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