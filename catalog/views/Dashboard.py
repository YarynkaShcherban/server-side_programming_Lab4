from django.shortcuts import render
from django.db.models import Avg
from store.models import Book
from ..ApiManager import *
import pandas as pd
from plotly.offline import plot
from bokeh.plotting import figure
from bokeh.embed import components
from bokeh.models import ColumnDataSource, HoverTool
import plotly.express as px
import plotly.graph_objects as go
from store.repositories.StatsRepo import StatsRepo
from store.views.benchmark_service import BenchmarkService
import time
from concurrent.futures import ThreadPoolExecutor
from math import pi


def get_main_stats():
    genres = genre_api.get_all_genres()
    all_stats = []

    for g in genres:
        genre_id = g['genre_id']
        books = book_api.get_books_by_genre(genre_id)

        prices = []

        for b in books:
            price = float(b.get('price'))
            prices.append(price)

        if prices:
            stats = {
                'price': prices,
                'genre': g['name'],
                'avg_price': round(sum(prices)/len(prices), 2),
                'median_price': round(pd.Series(prices).median(), 2),
                'min_price': min(prices),
                'max_price': max(prices)
            }
            all_stats.append(stats)

    return pd.DataFrame(all_stats)


def main_stats_figures():
    df = get_main_stats()
    if df.empty:
        return None
    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='Середнє',
        x=df['genre'],
        y=df['avg_price'],
        marker_color='#219ebc'
    ))

    fig.add_trace(go.Bar(
        name='Медіана',
        x=df['genre'],
        y=df['median_price'],
        marker_color='#fb8500'
    ))

    fig.add_trace(go.Bar(
        name='Мінімум',
        x=df['genre'],
        y=df['min_price'],
        marker_color='#2a9d8f'
    ))

    fig.add_trace(go.Bar(
        name='Максимум',
        x=df['genre'],
        y=df['max_price'],
        marker_color='#e63946'
    ))

    fig.update_layout(
        xaxis_title='Жанр',
        yaxis_title='Ціна (грн)',
        barmode='group',
        template='plotly_white',
        xaxis_tickangle=20,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        hovermode='x unified'
    )
    return fig


def get_dashboard_figures():
    template_style = 'plotly_white'

    line_chart_layout_updates = {
        'xaxis': {'gridcolor': '#e0e0e0', 'griddash': 'dash'},
        'yaxis': {'gridcolor': '#e0e0e0', 'griddash': 'dash'},
        'plot_bgcolor': 'white'
    }

    FONT_SIZE = "11pt"
    LABEL_FONT_SIZE = "12pt"
    TITLE_FONT_SIZE = "14pt"

    def apply_bokeh_styles(fig):
        fig.xaxis.major_label_text_font_size = FONT_SIZE
        fig.yaxis.major_label_text_font_size = FONT_SIZE
        fig.xaxis.axis_label_text_font_size = LABEL_FONT_SIZE
        fig.yaxis.axis_label_text_font_size = LABEL_FONT_SIZE
        fig.xaxis.axis_label_text_font_style = "bold"
        fig.yaxis.axis_label_text_font_style = "bold"
        return fig

    fig_main = main_stats_figures()
    # --- 1. Статистика по жанрах ---
    genres_data = list(StatsRepo.genres_with_books_and_avg_price())
    genres_df = pd.DataFrame(genres_data, columns=[
                             'name', 'num_books', 'avg_price'] if genres_data else [])

    if not genres_df.empty:
        genres_df['avg_price'] = genres_df['avg_price'].astype(float)

        # Кількість книг
        genres_count_df = genres_df.sort_values('num_books', ascending=False)
        fig_genres_count = px.bar(genres_count_df, x='name', y='num_books',

                                  labels={'name': 'Жанр',
                                          'num_books': 'Кількість книг'},
                                  template=template_style)
        fig_genres_count.update_traces(marker_color='#8ECAE6')

        data_genres_count = ColumnDataSource(genres_count_df)
        bokeh_genres_count = figure(x_axis_label="Жанр", y_axis_label="Кількість книг",
                                    x_range=genres_count_df['name'].tolist(), height=400,
                                    sizing_mode="stretch_width", output_backend="svg")
        bokeh_genres_count.vbar(x='name', top='num_books', width=0.7,
                                source=data_genres_count, fill_color="#8ECAE6")
        bokeh_genres_count.add_tools(HoverTool(
            tooltips=[("Жанр", "@name"), ("Кількість книг", "@num_books")]))
        apply_bokeh_styles(bokeh_genres_count)

        # Середня ціна
        genres_price_df = genres_df.sort_values('avg_price', ascending=False)
        fig_genres_price = px.line(genres_price_df, x='name', y='avg_price',

                                   labels={'name': 'Жанр',
                                           'avg_price': 'Середня ціна, грн'},
                                   template=template_style, markers=True)
        fig_genres_price.update_layout(line_chart_layout_updates)

        data_genres_price = ColumnDataSource(genres_price_df)
        bokeh_genres_price = figure(x_axis_label="Жанр", y_axis_label="Середня ціна, грн",
                                    x_range=genres_price_df['name'].tolist(), height=400,
                                    sizing_mode="stretch_width", output_backend="svg")
        bokeh_genres_price.line(
            x='name', y='avg_price', source=data_genres_price, line_width=3, color="#219ebc")
        bokeh_genres_price.add_tools(HoverTool(
            tooltips=[("Жанр", "@name"), ("Середня ціна, грн", "@avg_price")]))
        apply_bokeh_styles(bokeh_genres_price)

    # --- 2. Статистика по авторах ---
    authors_data = list(StatsRepo.authors_avg_book_price())
    authors_df = pd.DataFrame(authors_data, columns=[
                              'first_name', 'last_name', 'avg_price'] if authors_data else [])

    if not authors_df.empty:
        authors_df['avg_price'] = authors_df['avg_price'].astype(float)
        authors_price_df = authors_df.sort_values('avg_price', ascending=False)
        authors_price_df['full_name'] = authors_price_df['first_name'] + \
            ' ' + authors_price_df['last_name']
        fig_authors_price = px.line(authors_price_df, x='full_name', y='avg_price',

                                    labels={'full_name': 'Автор',
                                            'avg_price': 'Середня ціна, грн'},
                                    template=template_style,
                                    markers=True)
        fig_authors_price.update_layout(line_chart_layout_updates)
        fig_authors_price.update_traces(line_color='#f4a259')
        fig_authors_price.update_layout(xaxis={'tickangle': 45})

        data_authors_price = ColumnDataSource(authors_price_df)
        bokeh_authors_price = figure(x_axis_label="Автор", y_axis_label="Середня ціна, грн", x_range=authors_price_df['full_name'].tolist(), height=400,
                                     sizing_mode="stretch_width", output_backend="svg")
        bokeh_authors_price.vbar(x='full_name', top='avg_price',
                                 width=0.7, source=data_authors_price, color="#f4a259")
        bokeh_authors_price.add_tools(HoverTool(
            tooltips=[("Автор", "@full_name"), ("Середня ціна, грн", "@avg_price")]))
        bokeh_authors_price.xaxis.major_label_orientation = pi/4
        apply_bokeh_styles(bokeh_authors_price)

    # Топ авторів
    top_authors_data = list(StatsRepo.top_authors_by_book_count())
    top_authors_df = pd.DataFrame(top_authors_data, columns=[
                                  'first_name', 'last_name', 'num_books'] if top_authors_data else [])

    custom_colors = ['#22577a', '#38a3a5', '#57cc99', '#80ed99', '#c7f9cc']
    if not top_authors_df.empty:
        top_authors_df['full_name'] = top_authors_df['first_name'] + \
            ' ' + top_authors_df['last_name']
        fig_top_authors = px.pie(top_authors_df,
                                 values='num_books',
                                 names='full_name',
                                 template=template_style,
                                 color_discrete_sequence=custom_colors[:len(
                                     top_authors_df)],
                                 hole=0.3)

        data_top_authors = ColumnDataSource(top_authors_df)
        bokeh_top_authors = figure(x_axis_label="Кількість книг", y_axis_label="Автор", x_range=top_authors_df['full_name'].tolist(), height=400,
                                   sizing_mode="stretch_width", output_backend="svg")
        bokeh_top_authors.vbar(x='full_name', top='num_books',
                               source=data_top_authors, width=0.7, color='#57cc99')
        bokeh_top_authors.add_tools(HoverTool(
            tooltips=[("Автор", "@full_name"), ("Кількість книг", "@num_books")]))
        bokeh_top_authors.xaxis.major_label_orientation = pi/4
        apply_bokeh_styles(bokeh_top_authors)

    # --- 3. Статистика по видавництвах ---
    publishers_data = list(StatsRepo.publishers_avg_price())
    publishers_df = pd.DataFrame(publishers_data, columns=[
                                 'name', 'num_books', 'avg_price'] if publishers_data else [])

    if not publishers_df.empty:
        publishers_df['avg_price'] = publishers_df['avg_price'].astype(float)
        publishers_price_df = publishers_df.sort_values(
            'avg_price', ascending=False)
        fig_publishers_price = px.line(publishers_price_df, x='name', y='avg_price',
                                       labels={'name': 'Видавництво',
                                               'avg_price': 'Середня ціна, грн'},
                                       template=template_style,
                                       markers=True)
        fig_publishers_price.update_layout(
            line_chart_layout_updates)
        fig_publishers_price.update_traces(line_color='#2a9d8f')
        fig_publishers_price.update_layout(xaxis={'tickangle': 20})

        data_pub_price = ColumnDataSource(publishers_price_df)
        bokeh_pub_price = figure(x_axis_label="Видавництво", y_axis_label="Середня ціна, грн",
                                 x_range=publishers_price_df['name'].tolist(), height=400,
                                 sizing_mode="stretch_width", output_backend="svg")
        bokeh_pub_price.line(
            x='name', y='avg_price', source=data_pub_price, line_width=3, color='#2a9d8f')
        bokeh_pub_price.add_tools(HoverTool(
            tooltips=[("Видавництво", "@name"), ("Середня ціна, грн", "@avg_price")]))
        bokeh_pub_price.xaxis.major_label_orientation = pi/4
        apply_bokeh_styles(bokeh_pub_price)

    # Дорогі видавництва
    expensive_pub_data = list(StatsRepo.expensive_publishers())
    expensive_pub_df = pd.DataFrame(expensive_pub_data, columns=[
                                    'name', 'avg_price'] if expensive_pub_data else [])

    custom_colors_1 = ['#0d47a1', '#1565c0', '#1976d2', '#1e88e5', '#2196f3',
                       '#42a5f5', '#64b5f6', '#90caf9', '#bbdefb', '#e3f2fd']

    if not expensive_pub_df.empty:
        expensive_pub_df['avg_price'] = expensive_pub_df['avg_price'].astype(
            float)
        fig_expensive_pub = px.pie(expensive_pub_df, names='name', values='avg_price',
                                   title="Дорогі видавництва (розподіл за середньою ціною)",
                                   template=template_style,
                                   color_discrete_sequence=custom_colors_1[:len(
                                       expensive_pub_df)],
                                   hole=0.3)

        data_expensive_pub = ColumnDataSource(expensive_pub_df)
        bokeh_expensive_pub = figure(x_axis_label="Видавництво", y_axis_label="Середня ціна, грн", x_range=expensive_pub_df['name'].tolist(), height=400,
                                     sizing_mode="stretch_width", output_backend="svg")
        bokeh_expensive_pub.vbar(
            x='name', top='avg_price', source=data_expensive_pub, width=0.7, color='#1565c0')
        bokeh_expensive_pub.add_tools(HoverTool(
            tooltips=[("Видавництво", "@name"), ("Середня ціна, грн", "@avg_price")]))
        bokeh_expensive_pub.xaxis.major_label_orientation = pi/4
        apply_bokeh_styles(bokeh_expensive_pub)

    # --- 4. Статистика продажів ---
    stores_data = list(StatsRepo.store_sales_stats())
    stores_df = pd.DataFrame(stores_data, columns=[
                             'name', 'total_sales', 'total_purchases'] if stores_data else [])

    if not stores_df.empty:
        stores_df['total_sales'] = stores_df['total_sales'].astype(float)
        stores_sales_df = stores_df.sort_values('total_sales', ascending=False)
        fig_store_sales = px.bar(stores_sales_df, x='name', y='total_sales',

                                 labels={'name': 'Магазин',
                                         'total_sales': 'Сума продажів, грн'},
                                 template=template_style,
                                 color='total_sales',
                                 color_continuous_scale=px.colors.sequential.Viridis)

        data_store_sales = ColumnDataSource(stores_sales_df)
        bokeh_store_sales = figure(x_axis_label="Магазин", y_axis_label="Сума продажів, грн", x_range=stores_sales_df['name'].tolist(), height=400,
                                   sizing_mode="stretch_width", output_backend="svg")
        bokeh_store_sales.vbar(x='name', top='total_sales',
                               source=data_store_sales, width=0.7, color="#8ecae6")
        bokeh_store_sales.add_tools(HoverTool(
            tooltips=[("Магазин", "@name"), ("Сума продажів, грн", "@total_sales")]))

        apply_bokeh_styles(bokeh_store_sales)

        stores_count_df = stores_df.sort_values(
            'total_purchases', ascending=False)
        fig_store_count = px.line(stores_count_df, x='name', y='total_purchases',

                                  labels={'name': 'Магазин',
                                          'total_purchases': 'Кількість продажів'},
                                  template=template_style, markers=True)
        fig_store_count.update_layout(line_chart_layout_updates)
        fig_store_count.update_traces(line_color='#bc4b51')

        data_store_count = ColumnDataSource(stores_count_df)
        bokeh_store_count = figure(x_axis_label="Магазин", y_axis_label="Кількість продажів",
                                   x_range=stores_count_df['name'].tolist(), height=400,
                                   sizing_mode="stretch_width", output_backend="svg")

        bokeh_store_count.line(x='name', y='total_purchases',
                               source=data_store_count, line_width=3, color='#bc4b51')
        bokeh_store_count.add_tools(HoverTool(
            tooltips=[("Магазин", "@name"), ("Кількість продажів", "@total_purchases")]))
        apply_bokeh_styles(bokeh_store_count)

        bokeh_script_1, bokeh_div_1 = components(bokeh_genres_count)
        bokeh_script_2, bokeh_div_2 = components(bokeh_genres_price)
        bokeh_script_3, bokeh_authors_price_div = components(
            bokeh_authors_price)
        bokeh_script_4, bokeh_top_authors_div = components(bokeh_top_authors)
        bokeh_script_5, bokeh_pub_price_div = components(bokeh_pub_price)
        bokeh_script_6, bokeh_expensive_pub_div = components(
            bokeh_expensive_pub)
        bokeh_script_7, bokeh_store_sales_div = components(bokeh_store_sales)
        bokeh_script_8, bokeh_store_count_div = components(bokeh_store_count)

    return {
        'fig_main_stats': plot(fig_main, output_type='div') if fig_main else "<p>Немає даних</p>",
        'fig_genres_count': plot(fig_genres_count, output_type='div') if fig_genres_count else "<p>Немає даних</p>",
        'fig_genres_price': plot(fig_genres_price, output_type='div') if fig_genres_price else "<p>Немає даних</p>",
        'fig_authors_price': plot(fig_authors_price, output_type='div') if fig_authors_price else "<p>Немає даних</p>",
        'fig_top_authors': plot(fig_top_authors, output_type='div') if fig_top_authors else "<p>Немає даних</p>",
        'fig_publishers_price': plot(fig_publishers_price, output_type='div') if fig_publishers_price else "<p>Немає даних</p>",
        'fig_expensive_pub': plot(fig_expensive_pub, output_type='div') if fig_expensive_pub else "<p>Немає даних</p>",
        'fig_store_sales': plot(fig_store_sales, output_type='div') if fig_store_sales else "<p>Немає даних</p>",
        'fig_store_count': plot(fig_store_count, output_type='div') if fig_store_count else "<p>Немає даних</p>",
        "bokeh_genres_count_script": bokeh_script_1,
        "bokeh_genres_count_div": bokeh_div_1,
        "bokeh_genres_price_script": bokeh_script_2,
        "bokeh_genres_price_div": bokeh_div_2,
        "bokeh_authors_price_script": bokeh_script_3,
        "bokeh_authors_price_div": bokeh_authors_price_div,
        "bokeh_top_authors_script": bokeh_script_4,
        "bokeh_top_authors_div": bokeh_top_authors_div,
        "bokeh_publishers_price_script": bokeh_script_5,
        "bokeh_publishers_price_div": bokeh_pub_price_div,
        "bokeh_expensive_pub_script": bokeh_script_6,
        "bokeh_expensive_pub_div": bokeh_expensive_pub_div,
        "bokeh_store_sales_script": bokeh_script_7,
        "bokeh_store_sales_div": bokeh_store_sales_div,
        "bokeh_store_count_script": bokeh_script_8,
        "bokeh_store_count_div": bokeh_store_count_div
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
            chunks = [all_ids[i:i + chunk_size]
                      for i in range(0, len(all_ids), chunk_size)]
            start_time = time.time()
            with ThreadPoolExecutor(max_workers=n) as executor:
                list(executor.map(get_segment_avg, chunks))
            async_results.append(
                {'threads': n, 'execution_time': time.time() - start_time})

        df_async = pd.DataFrame(async_results)
        idx_min = df_async['execution_time'].idxmin()
        fig_async = px.line(
            df_async,
            x='threads',
            y='execution_time',
            title="Вплив кількості потоків на час обробки",
            labels={'threads': 'Кількість потоків',
                    'execution_time': 'Час виконання (сек)'},
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