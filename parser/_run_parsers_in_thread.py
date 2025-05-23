def _run_parsers_in_thread(params):
    """Выполнение парсинга в отдельном потоке"""
    try:
        results = {'hh': None, 'habr': None, 'superjob': None}
        
        def fetch_hh():
            try:
                internships = fetch_hh_internships(**params)
                logger.info(f"Получено {len(internships)} стажировок с HeadHunter.")
                results['hh'] = internships
            except Exception as e:
                logger.error(f"Ошибка при получении стажировок с HeadHunter: {str(e)}")
                results['hh'] = []
        
        def fetch_habr():
            try:
                internships = fetch_habr_career_internships(**params)
                logger.info(f"Получено {len(internships)} стажировок с Habr Career.")
                results['habr'] = internships
            except Exception as e:
                logger.error(f"Ошибка при получении стажировок с Habr Career: {str(e)}")
                results['habr'] = []
                
        def fetch_superjob():
            try:
                internships = fetch_superjob_internships(**params)
                logger.info(f"Получено {len(internships)} стажировок с SuperJob.")
                results['superjob'] = internships
            except Exception as e:
                logger.error(f"Ошибка при получении стажировок с SuperJob: {str(e)}")
                results['superjob'] = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            hh_future = executor.submit(fetch_hh)
            habr_future = executor.submit(fetch_habr)
            superjob_future = executor.submit(fetch_superjob)
            
            concurrent.futures.wait([hh_future, habr_future, superjob_future])
        
        hh_internships = results['hh'] or []
        habr_internships = results['habr'] or []
        superjob_internships = results['superjob'] or []
        
        hh_website, _ = Website.objects.get_or_create(
            name="HeadHunter",
            url="https://hh.ru/",
        )
        
        habr_website, _ = Website.objects.get_or_create(
            name="Habr Career",
            url="https://career.habr.com/",
        )
        
        superjob_website, _ = Website.objects.get_or_create(
            name="SuperJob",
            url="https://www.superjob.ru/",
        )
        
        hh_client = HeadHunterAPI()
        habr_client = HabrCareerParser()
        superjob_client = SuperJobParser()
        
        stats = {
            'hh': {'total': len(hh_internships), 'created': 0, 'updated': 0, 'errors': 0},
            'habr': {'total': len(habr_internships), 'created': 0, 'updated': 0, 'errors': 0},
            'superjob': {'total': len(superjob_internships), 'created': 0, 'updated': 0, 'errors': 0}
        }
        
        for item in hh_internships:
            if isinstance(item, dict):
                obj, is_created = hh_client.create_internship(item, hh_website)
                if obj:
                    if is_created:
                        stats['hh']['created'] += 1
                    else:
                        stats['hh']['updated'] += 1
                else:
                    stats['hh']['errors'] += 1
            elif isinstance(item, Internship):
                stats['hh']['updated'] += 1
            else:
                logger.warning(f"Неизвестный тип данных от HeadHunter: {type(item)}")
                stats['hh']['errors'] += 1
        
        for item in habr_internships:
            if isinstance(item, dict):
                obj, is_created = habr_client.create_internship(item, habr_website)
                if obj:
                    if is_created:
                        stats['habr']['created'] += 1
                    else:
                        stats['habr']['updated'] += 1
                else:
                    stats['habr']['errors'] += 1
            elif isinstance(item, Internship):
                stats['habr']['updated'] += 1
            else:
                logger.warning(f"Неизвестный тип данных от Habr Career: {type(item)}")
                stats['habr']['errors'] += 1
        
        for item in superjob_internships:
            if isinstance(item, dict):
                obj, is_created = superjob_client.create_internship(item, superjob_website)
                if obj:
                    if is_created:
                        stats['superjob']['created'] += 1
                    else:
                        stats['superjob']['updated'] += 1
                else:
                    stats['superjob']['errors'] += 1
            elif isinstance(item, Internship):
                stats['superjob']['updated'] += 1
            else:
                logger.warning(f"Неизвестный тип данных от SuperJob: {type(item)}")
                stats['superjob']['errors'] += 1
        
        total_count = len(hh_internships) + len(habr_internships) + len(superjob_internships)
        logger.info(f"Параллельно обработано {total_count} стажировок через webhook")
    except Exception as e:
        logger.error(f"Ошибка при выполнении параллельного парсинга через webhook: {str(e)}") 