from django.shortcuts import render, redirect
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from .models import Website, Internship, SearchQuery
from .forms import WebsiteForm, InternshipFilterForm
from .tasks import run_hh_api_parser, parse_all_internships
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from dotenv import load_dotenv
from .hh_api_parser import HeadHunterAPI
import os
import json
from django.views import View
import logging
from django.db.models import Q
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods
import threading

logger = logging.getLogger(__name__)

load_dotenv()

def index(request):
    """Главная страница с вкладками"""
    websites = Website.objects.all()
    return render(request, 'parser/main-page/main-page.html', {'websites': websites})

class WebsiteListView(ListView):
    """Отображение списка сайтов"""
    model = Website
    template_name = 'parser/website_list.html'
    context_object_name = 'websites'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['hh_enabled'] = True
        return context

class WebsiteCreateView(View):
    """
    Создание нового сайта и связанной с ним стажировки через AJAX (JSON).
    """
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body.decode('utf-8'))
            
            site_name = data.get('name')
            site_url = data.get('url')

            if not site_name or not site_url:
                return JsonResponse({'status': 'error', 'message': 'Имя и URL сайта обязательны.'}, status=400)

            website, website_created = Website.objects.get_or_create(
                url=site_url,
                defaults={'name': site_name}
            )
            if not website_created and website.name != site_name:
                website.name = site_name
                website.save(update_fields=['name'])
            
            action_site = "создан" if website_created else "найден/обновлен"
            
            internship_title = data.get('title')
            internship_position = data.get('position')
            internship_company = data.get('company')
            internship_description = data.get('description')
            js_start_date = data.get('start_date') if data.get('start_date') else None
            js_end_date = data.get('end_date') if data.get('end_date') else None
            internship_technologies = data.get('technologies')
            internship_city = data.get('city')
            internship_salary = data.get('salary')

            if not internship_title or not internship_company or not internship_position:
                 logger.warning(f"Недостаточно данных для сохранения стажировки (title, company или position отсутствуют) для сайта {site_url}")
                 return JsonResponse({
                     'status': 'success', 
                     'message': f'Сайт "{website.name}" {action_site}, но данные стажировки не были сохранены (не все обязательные поля заполнены).',
                     'website_id': website.id
                 })

            internship_defaults = {
                'title': internship_title,
                'position': internship_position,
                'company': internship_company,
                'description': internship_description,
                'source_website': website, 
                'url': site_url, 
            }
            
            if js_start_date:
                internship_defaults['selection_start_date'] = js_start_date
            if js_end_date:
                internship_defaults['selection_end_date'] = js_end_date
            if internship_city:
                internship_defaults['city'] = internship_city
            if internship_salary:
                internship_defaults['salary'] = internship_salary

            if internship_technologies and isinstance(internship_technologies, list):
                 internship_defaults['keywords'] = ', '.join(filter(None, internship_technologies))

            internship, internship_created = Internship.objects.update_or_create(
                url=site_url, 
                source_website=website,
                defaults=internship_defaults
            )
            action_internship = "создана" if internship_created else "обновлена"

            return JsonResponse({
                'status': 'success', 
                'message': f'Сайт "{website.name}" {action_site}, стажировка "{internship.title}" {action_internship}.',
                'website_id': website.id,
                'internship_id': internship.id
            })

        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Ошибка декодирования JSON.'}, status=400)
        except Exception as e:
            logger.error(f"Ошибка в WebsiteCreateView: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': f'Внутренняя ошибка сервера: {str(e)}'}, status=500)

class WebsiteDeleteView(View):
    """
    Удаление сайта и связанных с ним стажировок через AJAX (JSON).
    """
    def delete(self, request, pk, *args, **kwargs):
        try:
            website = Website.objects.get(pk=pk)
            if website.is_special:
                return JsonResponse({'status': 'error', 'message': 'Этот сайт нельзя удалить.'}, status=403)
            
            site_name = website.name
            website.delete()
            
            return JsonResponse({
                'status': 'success',
                'message': f'Сайт "{site_name}" и все связанные с ним стажировки были успешно удалены.'
            })
        except Website.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Сайт не найден.'}, status=404)
        except Exception as e:
            logger.error(f"Ошибка в WebsiteDeleteView: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': f'Внутренняя ошибка сервера: {str(e)}'}, status=500)

def parse_website_preview(request):
    """Предпросмотр результатов парсинга сайта"""
    return JsonResponse({
        'success': False, 
        'error': 'Функциональность парсинга веб-сайтов временно недоступна. Используйте API HeadHunter.'
    })

def save_internship(request):
    """Сохранение стажировки после предпросмотра"""
    if request.method == 'POST':
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

def run_hh_parser(request):
    """Ручной запуск парсера HeadHunter"""
    if request.method == 'POST':
        try:
            result = run_hh_api_parser()
            if result:
                messages.success(request, 'Парсер HeadHunter успешно выполнен')
            else:
                messages.warning(request, 'Парсер HeadHunter не нашел новых стажировок')
        except Exception as e:
            messages.error(request, f'Ошибка при запуске парсера HeadHunter: {str(e)}')
        
        return redirect('parser:internship_list')
    
    return redirect('parser:website_list')

class InternshipListView(ListView):
    """Отображение списка стажировок с фильтрами"""
    model = Internship
    template_name = 'parser/second-page/second-page.html'
    context_object_name = 'internships'
    paginate_by = 10

    def get_queryset(self):
        queryset = Internship.objects.filter(is_archived=False).order_by('-created_at')
        
        filter_form = InternshipFilterForm(self.request.GET)
        if filter_form.is_valid():
            queryset = self.apply_filters(queryset, filter_form.cleaned_data)
        elif filter_form.errors:
             logger.warning(f"InternshipListView: Filter form is invalid. Errors: {filter_form.errors}, GET params: {self.request.GET}")
        return queryset
    
    def apply_filters(self, queryset, filter_data):
        keywords = filter_data.get('keywords')
        if keywords:
            queryset = queryset.filter(
                Q(keywords__icontains=keywords) |
                Q(description__icontains=keywords) |
                Q(company__icontains=keywords)
            )
        
        start_date = filter_data.get('start_date')
        if start_date:
            queryset = queryset.filter(selection_start_date__gte=start_date)
        
        format_type = filter_data.get('format')
        if format_type:
            queryset = queryset.filter(employment_type=format_type)
        
        city = filter_data.get('city')
        if city:
            queryset = queryset.filter(city__icontains=city)
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs) 
        if not context.get('page_obj'):
            paginator = context.get('paginator')
            if paginator is None:
                logger.error("InternshipListView: Neither page_obj nor paginator found in context. Pagination is not working.")
            else:
                logger.error(f"InternshipListView: page_obj not found, but paginator is present (paginator.num_pages: {paginator.num_pages}, paginator.count: {paginator.count}). Queryset might be empty or page number out of range.")

        context['filter_form'] = InternshipFilterForm(self.request.GET)
        
        all_cities_entries = Internship.objects.values_list('city', flat=True)
        unique_cities = set()
        for city_entry in all_cities_entries:
            if city_entry:
                cities_list = [city.strip() for city in city_entry.split(',') if city.strip()]
                unique_cities.update(cities_list)
        context['cities'] = sorted(list(unique_cities))
        
        return context

    def render_to_response(self, context, **response_kwargs):
        page_obj_for_ajax = context.get('page_obj')

        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            if not page_obj_for_ajax:
                logger.warning("InternshipListView (AJAX): page_obj is missing in context! Returning empty list for AJAX.")
                return JsonResponse({'html': '', 'has_next': False})
            
            html = render_to_string(
                'parser/partials/internship_item_list.html',
                {'internships': page_obj_for_ajax.object_list, 'page_obj': page_obj_for_ajax}
            )
            return JsonResponse({'html': html, 'has_next': page_obj_for_ajax.has_next()})
        
        return super().render_to_response(context, **response_kwargs)

class ArchivedInternshipListView(InternshipListView):
    """Отображение архивных стажировок"""
    def get_queryset(self):
        queryset = Internship.objects.filter(is_archived=True).order_by('-created_at')
        filter_form = InternshipFilterForm(self.request.GET)
        if filter_form.is_valid():
            queryset = self.apply_filters(queryset, filter_form.cleaned_data)
        return queryset

def archive_internship(request, pk):
    """Перемещение стажировки в архив"""
    if request.method == 'POST':
        try:
            internship = Internship.objects.get(pk=pk)
            internship.is_archived = True
            internship.save()
            return JsonResponse({'success': True})
        except Internship.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Internship not found'})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

class MainPageView(TemplateView):
    template_name = 'parser/main-page/main-page.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['websites'] = Website.objects.all()
        return context

class SecondPageView(InternshipListView):
    template_name = 'parser/second-page/second-page.html'

class AddSiteModalView(TemplateView):
    template_name = 'parser/modal-pages/add-site/add-site.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['websites'] = Website.objects.all()
        return context

@require_http_methods(["GET"])
def get_special_parsers_settings(request):
    """
    Возвращает текущие уникальные ключевые слова и города из SearchQuery.
    """
    try:
        keywords_qs = SearchQuery.objects.exclude(keywords__isnull=True).exclude(keywords__exact='').values_list('keywords', flat=True).distinct()
        cities_qs = SearchQuery.objects.exclude(city__isnull=True).exclude(city__exact='').values_list('city', flat=True).distinct()


        all_keywords = set()
        for sq in SearchQuery.objects.filter(keywords__isnull=False).exclude(keywords__exact=''):
            all_keywords.add(sq.keywords)
            
        all_cities = set()
        for sq in SearchQuery.objects.filter(city__isnull=False).exclude(city__exact=''):
            all_cities.add(sq.city)

        return JsonResponse({
            "keywords": sorted(list(all_keywords)),
            "cities": sorted(list(all_cities))
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def save_special_parsers_settings(request):
    """
    Обновляет настройки поисковых запросов (ключевые слова и города).
    Удаляет отсутствующие комбинации, добавляет новые.
    Для каждой новой или измененной комбинации запускает парсер parse_all_internships асинхронно.
    """
    try:
        data = json.loads(request.body)
        current_keywords_from_user = set(kw.strip().lower() for kw in data.get("keywords", []) if kw.strip())
        current_cities_from_user = set(c.strip().lower() for c in data.get("cities", []) if c.strip())

        desired_combinations = set()
        if current_keywords_from_user and current_cities_from_user:
            for city in current_cities_from_user:
                for keyword in current_keywords_from_user:
                    desired_combinations.add((city, keyword))
        elif current_keywords_from_user:
            for keyword in current_keywords_from_user:
                desired_combinations.add((None, keyword))
        elif current_cities_from_user:
            for city in current_cities_from_user:
                desired_combinations.add((city, None))

        existing_queries_in_db = SearchQuery.objects.all()
        db_combinations = set()
        for sq in existing_queries_in_db:
            city_in_db = sq.city.lower() if sq.city else None
            keyword_in_db = sq.keywords.lower() if sq.keywords else None
            db_combinations.add((city_in_db, keyword_in_db))

        queries_to_delete = db_combinations - desired_combinations
        deleted_count = 0
        for city_to_del, kw_to_del in queries_to_delete:
            SearchQuery.objects.filter(city__iexact=city_to_del if city_to_del else None, 
                                       keywords__iexact=kw_to_del if kw_to_del else None).delete()
            deleted_count +=1
            logger.info(f"Удален поисковый запрос: Город='{city_to_del}', Ключевое слово='{kw_to_del}'")

        queries_to_parse_params = []
        created_count = 0

        for city_desired, kw_desired in desired_combinations:
            query, created = SearchQuery.objects.get_or_create(
                city__iexact=city_desired if city_desired else None,
                keywords__iexact=kw_desired if kw_desired else None,
                defaults={
                    'city': city_desired,
                    'keywords': kw_desired,
                    'max_pages': 10, 
                    'last_executed': None
                }
            )
            if created:
                created_count += 1
                queries_to_parse_params.append({"city": city_desired, "keywords": kw_desired, "max_pages": query.max_pages})
            else:
                pass

        threads = []
        triggered_parsing_count = 0
        parsing_info_for_user = []

        if queries_to_parse_params:
            for params in queries_to_parse_params:
                logger.info(f"[ПАРСЕР] Асинхронный запуск parse_all_internships для: Город='{params['city']}', Ключевое слово='{params['keywords']}'")
                thread = threading.Thread(target=parse_all_internships, 
                                          kwargs={'city': params['city'], 
                                                  'keywords': params['keywords'], 
                                                  'max_pages': params['max_pages']})
                threads.append(thread)
                thread.start()
                triggered_parsing_count += 1
                SearchQuery.objects.filter(
                    city__iexact=params['city'] if params['city'] else None, 
                    keywords__iexact=params['keywords'] if params['keywords'] else None
                ).update(last_executed=timezone.now())
                parsing_info_for_user.append(f"Город: {params['city'] or '-'}, Ключ: {params['keywords'] or '-'}")
        
        for city_desired, kw_desired in desired_combinations:
            was_just_parsed = False
            for parsed_param in queries_to_parse_params:
                parsed_city = parsed_param['city']
                parsed_kw = parsed_param['keywords']
                if (city_desired == parsed_city or (not city_desired and not parsed_city)) and \
                   (kw_desired == parsed_kw or (not kw_desired and not parsed_kw)):
                    was_just_parsed = True
                    break
            
            if not was_just_parsed:
                 SearchQuery.objects.filter(
                     city__iexact=city_desired if city_desired else None, 
                     keywords__iexact=kw_desired if kw_desired else None
                 ).update(last_executed=timezone.now())

        message = "Настройки особых парсеров обновлены."
        if deleted_count > 0:
            message += f" Удалено старых запросов: {deleted_count}."
        if created_count > 0:
            message += f" Добавлено новых запросов: {created_count}."
        if triggered_parsing_count > 0:
            message += f" Запущен парсинг для {triggered_parsing_count} новых комбинаций."
        elif not created_count and not deleted_count:
             message = "Настройки не изменились. Парсинг не запустился"
        
        return JsonResponse({"message": message})

    except json.JSONDecodeError:
        return JsonResponse({"error": "Некорректный JSON"}, status=400)
    except Exception as e:
        logger.error(f"Критическая ошибка в save_special_parsers_settings: {e}", exc_info=True)
        return JsonResponse({"error": f"Внутренняя ошибка сервера: {str(e)}"}, status=500)

@require_http_methods(["DELETE"])
def delete_internship(request, internship_id):
    try:
        internship = Internship.objects.get(id=internship_id)
        internship.delete()
        return JsonResponse({'status': 'success', 'message': 'Стажировка удалена'})
    except Internship.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Стажировка не найдена'}, status=404)
    except Exception as e:
        logger.error(f"Ошибка при удалении стажировки: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
