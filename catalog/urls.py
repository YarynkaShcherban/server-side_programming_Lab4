from django.urls import path
from .views.Book import (
    book_list, book_create, book_list_by_genre, 
    book_list_by_publisher, book_update, book_delete, 
    book_stats, book_detail, avg_price_by_genre_store
)
from .views.Dashboard import (
    dashboard_page, dashboard_view,  
    benchmark_view, genres_stats_api, authors_avg_price_api,
    publishers_stats_api, top_authors_api, expensive_publishers_api,
    store_sales_api
)
from .ApiManager import book_overall_stats, genre_stats, publisher_stats

app_name = "catalog"

urlpatterns = [
    path('', book_list, name='book_list'),
    path('create/', book_create, name='book_create'),
    path('genre/<int:genre_id>/', book_list_by_genre,
         name='book_list_by_genre'),
    path('publisher/<int:publisher_id>/',
         book_list_by_publisher, name='book_list_by_publisher'),
    #     path('<int:book_id>/', views.book_detail, name='book_detail'),
    path('<int:book_id>/edit/', book_update, name='book_update'),
    path('<int:book_id>/delete/', book_delete, name='book_delete'),
    path('stats/', book_stats, name='book_stats'),
    path('<int:book_id>/details/', book_detail, name='book_detail'),
    path("books/stats/overall/", book_overall_stats),
    path("genres/stats/", genre_stats),
    path("publishers/stats/", publisher_stats),
    path('stats/genres/', genres_stats_api, name='genres_stats_api'),
    path('stats/authors/', authors_avg_price_api, name='authors_avg_price_api'),
    path('stats/publishers/', publishers_stats_api, name='publishers_stats_api'),
    path('stats/top_authors/', top_authors_api, name='top_authors_api'),
    path('stats/expensive_publishers/', expensive_publishers_api, name='expensive_publishers_api'),
    path('stats/store_sales/', store_sales_api, name='store_sales_api'),
    path('dashboard/page/', dashboard_page, name='dashboard_page'),
    path('dashboard/api/', dashboard_view, name='dashboard_api'),
    path('avg-price-by-genre-store/', avg_price_by_genre_store, name='avg_price_by_genre_store'),
    path('benchmark/', benchmark_view, name='benchmark_page'),
]