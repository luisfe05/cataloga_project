/**
 * lang/es.js
 *
 * Spanish (Latin America, es-419) text for every label, button, and
 * message in the app. Must have the same keys as en.js.
 * Words in braces, like {n} or {path}, are filled in by t() in i18n.js.
 */

const LANG_ES = {
    // Navigation and header
    "nav.home": "Inicio",
    "nav.catalog": "Lista del catálogo",
    "home.view_icons": "Íconos",
    "home.view_columns": "Columnas",
    "home.path": "Ruta",
    "home.files": "{n} archivos",
    "home.folders": "{n} carpetas",
    "home.classified": "{n} clasificados",
    "home.manual_review": "{n} en revisión manual",
    "home.not_cataloged": "Sin catalogar",
    "home.empty": "Esta carpeta está vacía.",
    "home.load_failed": "No se pudo leer la carpeta.",
    "home.double_click": "Doble clic o Enter para abrir una carpeta.",
    "home.kind": "Tipo",
    "home.kind_folder": "Carpeta",
    "home.kind_photo": "Foto",
    "home.contains": "Contiene",
    "home.status": "Estado",
    "home.cataloged": "Catalogado",
    "home.date": "Fecha",
    "home.no_date": "Sin fecha",
    "home.date_from": "Fecha de",
    "home.source": "Fuente",
    "home.summary": "Resumen",
    "home.why": "Por qué esta carpeta",
    "home.open": "Abrir",
    "home.show": "Mostrar en la carpeta",
    "nav.projects": "Proyectos",
    "nav.plan": "Por aprobar",
    "nav.dashboard": "Panel",
    "nav.settings": "Configuración",
    "header.no_project": "Todavía no hay proyecto",

    // Catalog
    "catalog.tab_all": "Todos los archivos",
    "catalog.tab_review": "Revisión manual {n}",
    "catalog.search": "Buscar en el catálogo",
    "catalog.filter_type_all": "Tipo de medio: todos",
    "catalog.filter_source_all": "Fuente: todas",
    "catalog.newest_first": "Más recientes primero",
    "catalog.newest_first_clear": "Volver al orden normal",
    "catalog.download": "Hoja",
    "catalog.edit_mode": "Modo edición",
    "catalog.col_original": "Nombre original",
    "catalog.col_filename": "Nombre del archivo",
    "catalog.col_type": "Tipo de medio",
    "catalog.col_source": "Fuente",
    "catalog.col_date": "Fecha",
    "catalog.col_summary": "Resumen",
    "catalog.col_status": "Estado",
    "summary.read_more": "Leer más",
    "summary.show_less": "Ver menos",
    "catalog.summary_placeholder": "Resumen manual",
    "catalog.saving": "Guardando...",
    "catalog.saving_summary":
        "Guardando y actualizando el resumen con tu cambio...",
    "catalog.saved": "Guardado.",
    "catalog.saved_summary": "Guardado. El resumen se actualizó con tu cambio.",
    "catalog.edit_banner": "Editando. Haz clic en una celda para cambiarla. "
        + "Se guarda al salir de la celda o al presionar Enter. La "
        + "actualización automática está en pausa.",
    "catalog.summary_limit": "El resumen puede tener hasta 100 caracteres.",
    "catalog.old_inbox_warning": "Tu carpeta Inbox vieja todavía tiene "
        + "archivos. Muévelos a la Drop Zone para catalogarlos.",
    "catalog.no_folder": "Ve a Configuración para elegir el proveedor de IA.",
    "catalog.empty": "Pon archivos en la carpeta Drop Zone dentro de "
        + "{path}. Aparecerán aquí cuando se clasifiquen.",
    "catalog.no_match": "Ningún archivo coincide con tu búsqueda.",
    "scan.paused": "En pausa en {done} de {total} archivos.",
    "scan.stopped": "Lectura detenida en {done} de {total}",
    "banner.not_cataloged": "Esta carpeta todavía no está catalogada.",
    "banner.listed": "Cataloga listó {total} archivos sin leerlos. Empieza cuando quieras.",
    "banner.learn": "Aprender de mi carpeta",
    "banner.catalog_now": "Archivar ahora",
    "banner.learned": "Se aprendieron {n} carpetas de tu carpeta.",
    "scan.retry_title": "Algunos archivos no se pudieron leer.",
    "plan.catalog_only": "Catalog only: no plan",
    "plan.no_plan": "Este proyecto ordena por tipo de archivo, así que no "
        + "tiene plan.",
    "plan.empty": "Nada que hacer: cada archivo está donde debe.",
    "plan.load_failed": "No se pudo cargar el plan.",
    "plan.filter_folder_all": "Destino: Todos",
    "plan.filter_action_all": "Acción: Todas",
    "plan.filter_review": "Revisión manual",
    "plan.filter_unchanged": "Sin cambios",
    "plan.action_move": "Mover",
    "plan.action_rename": "Renombrar",
    "plan.action_move_rename": "Mover y renombrar",
    "plan.action_create_folder": "Carpeta nueva",
    "plan.action_none": "Sin cambios",
    "plan.search": "Buscar en el plan",
    "plan.approve_all": "Aprobar todo",
    "plan.approve_selected": "Aprobar seleccionados",
    "plan.skip_selected": "Saltar seleccionados",
    "plan.apply": "Aplicar cambios",
    "plan.apply_one": "Aplicar 1 cambio",
    "plan.apply_many": "Aplicar {n} cambios",
    "plan.tab_files": "Archivos",
    "plan.unread": "{n} archivos no se han leído todavía. Usa Archivar "
        + "ahora en Inicio; las propuestas aparecen aquí.",
    "plan.drop_zone": "Este proyecto archiva documentos desde su Drop Zone, "
        + "así que no hay propuestas que aprobar.",
    "plan.resume": "Continuar",
    "plan.undo": "Deshacer este lote",
    "plan.col_file": "Archivo",
    "plan.col_current": "Carpeta actual",
    "plan.col_proposed": "Carpeta propuesta",
    "plan.col_name": "Nombre propuesto",
    "plan.col_why": "Por qué",
    "plan.root": "Carpeta del proyecto",
    "plan.same_folder": "Misma carpeta",
    "plan.keep_name": "Mismo nombre",
    "plan.status_proposed": "Propuesto",
    "plan.status_approved": "Aprobado",
    "plan.status_skipped": "Saltado",
    "plan.status_pending": "En curso",
    "plan.status_applied": "Aplicado",
    "plan.status_failed": "Falló",
    "plan.status_undo_pending": "Deshaciendo",
    "plan.status_undone": "Deshecho",
    "plan.status_unchanged": "Sin cambios",
    "plan.approved_count": "{n} filas aprobadas.",
    "plan.applying": "Aplicando: {done} de {total} hechos, {failed} fallaron.",
    "plan.undoing": "Deshaciendo: {done} de {total} devueltos.",
    "plan.paused": "Este lote se pausó: {note}. {done} de {total} hechos.",
    "plan.applied": "Aplicado: {done} de {total} hechos, {failed} fallaron.",
    "plan.started": "Aplicando el plan…",
    "plan.undo_started": "Deshaciendo el lote…",
    "plan.folders": "Carpetas",
    "plan.leave": "Dejar como está",
    "plan.folders_hint": "Los archivos de una carpeta marcada Dejar como está "
        + "se catalogan, pero nunca se propone moverlos ni renombrarlos.",
    "plan.batches": "Lotes",
    "plan.batch_line": "Lote {id}, {date}: {applied} aplicados, {failed} "
        + "fallaron, {undone} deshechos.",
    "plan.filed_without_asking": "Archivado sin preguntar",
    "plan.note_disk": "La carpeta del proyecto no está disponible",
    "plan.note_interrupted": "La app se cerró mientras se aplicaba este lote",
    "error.plan_applying": "Se está aplicando o deshaciendo un lote. Espera a "
        + "que termine.",
    "error.batch_not_ready": "Este lote no se puede aplicar ni deshacer ahora.",
    "error.nothing_approved": "Aprueba al menos una fila primero.",
    "scan.stalled": "La lectura se trabó en {file}. Continúa para intentarlo de nuevo.",
    "scan.retry": "Reintentar los archivos sin terminar ({count})",
    "scan.loading": "Cargando documentos",
    "scan.running": "Leyendo {file}",
    "scan.still_reading": "Todavía leyendo este archivo… {file}",
    "scan.pause": "Pausar",
    "scan.resume": "Continuar",
    "catalog.progress_percent": "{n}% clasificado",
    "catalog.load_failed": "No se pudo cargar el catálogo: {message}",
    "catalog.backend_down": "el servidor de la app no responde.",
    "catalog.export_saved": "Hoja de cálculo guardada en {path}",
    "catalog.export_failed": "No se pudo guardar la hoja de cálculo.",
    "catalog.filter_category_all": "Categoría: todas",
    "catalog.filter_subcategory_all": "Subcategoría: todas",
    "catalog.more_columns": "Más columnas",
    "catalog.col_category": "Categoría",
    "catalog.col_subcategory": "Subcategoría",
    "catalog.col_keywords": "Palabras clave",
    "catalog.col_counterparty": "Contraparte",
    "catalog.col_confidentiality": "Confidencialidad",
    "catalog.col_owner": "Responsable",
    "catalog.col_effective_start": "Vigencia desde",
    "catalog.col_effective_end": "Vigencia hasta",
    "catalog.col_date_from": "Origen de la fecha",
    "catalog.date_from_photo": "Foto (toma)",
    "catalog.date_from_content": "Contenido",
    "catalog.date_from_metadata": "Metadata del archivo",
    "catalog.date_from_file": "Fecha del archivo",
    "catalog.date_from_photo_stamp": "Sello en la foto",
    "catalog.date_from_name": "Nombre del archivo o carpeta",
    "catalog.col_folder_reason": "Por qué esta carpeta",
    "catalog.col_confidence": "Confianza",
    "catalog.confidence_high": "Alta",
    "catalog.confidence_medium": "Media",
    "catalog.confidence_low": "Baja",
    "catalog.note_low_confidence": "Confianza baja",
    "catalog.not_in_list": "{value} (no está en la lista)",
    "catalog.note_duplicate": "Duplicado de {name}",
    "catalog.note_no_category": "La categoría no está en la lista del proyecto",
    "catalog.note_no_folder": "Ninguna carpeta encaja con este archivo",
    "catalog.col_folder": "Carpeta",
    "catalog.filter_folder_all": "Carpeta: todas",
    "catalog.filter_subfolder_all": "Subcarpeta: todas",
    "catalog.in_drop_zone": "Drop Zone",
    "catalog.suggested_folder": "Sugerida: {folder}",
    "catalog.proposed": "Propuesto: {folder} / {name}",
    "catalog.same_folder": "misma carpeta",
    "catalog.create_and_move": "Crear carpeta y mover",
    "catalog.move_to": "Mover a…",
    "catalog.moving": "Moviendo...",
    "catalog.moved": "Movido a {folder}",
    "catalog.note_media": "Audio y video necesitan una key de Gemini en Settings",
    "catalog.note_media_length":
        "Audio y video necesitan una key de Gemini en Settings. Duración {length}",
    "catalog.note_image": "No se pudo leer la imagen",
    "catalog.note_scan": "No se pudieron leer las páginas escaneadas",
    "catalog.note_timeout": "Se acabó el tiempo al leerlo",
    "catalog.note_cut_off": "La respuesta de la AI quedó cortada",
    "catalog.note_language_en": "La AI escribió el resumen en otro idioma dos veces, así que no se guardó. Escríbelo en inglés, o vuelve a generarlo editando la fuente o la fecha.",
    "catalog.note_language_es": "La AI escribió el resumen en otro idioma dos veces, así que no se guardó. Escríbelo en español, o vuelve a generarlo editando la fuente o la fecha.",
    "catalog.note_icloud": "En iCloud, sin descargar",
    "catalog.secret_hidden": "1 secreto tapado antes de enviar",
    "catalog.secrets_hidden": "{n} secretos tapados antes de enviar",
    "catalog.note_too_big": "El archivo pesa más de 50 MB y no se leyó",
    "catalog.note_topic": "No se encontró un tema en la foto",
    "catalog.note_missing": "Falta: {fields}",
    "catalog.keywords_limit": "Usa hasta 5 palabras clave, separadas por "
        + "comas, de hasta 40 caracteres cada una.",
    "catalog.counterparty_limit":
        "La contraparte puede tener hasta 100 caracteres.",
    "catalog.date_format": "Escribe la fecha como AAAA-MM-DD, por ejemplo "
        + "2026-07-15.",

    // Dashboard
    "dash.classified": "Documentos clasificados",
    "dash.activity": "Actividad reciente",
    "dash.empty": "Todavía no hay actividad. Pon archivos en la Drop Zone "
        + "para empezar.",
    "dash.review_button": "Ir a revisar",
    "dash.load_failed": "No se pudo cargar el panel: {message}",
    "dash.of_total": "de {n} documentos",
    "dash.no_documents": "Todavía no hay documentos",

    // Chat
    "chat.open_label": "Abrir el asistente de Cataloga",
    "chat.title": "Pregúntale a Cataloga",
    "chat.close": "Cerrar",
    "chat.empty_title": "¿En qué te ayudo con este proyecto?",
    "chat.empty_hint": "Nunca renombro un archivo sin tu confirmación.",
    "chat.example_summary": "Resume este proyecto",
    "chat.example_press": "Busca recortes de prensa",
    "chat.example_review": "Muestra lo que está en revisión manual",
    "chat.example_rename": "Renombra un archivo",
    "chat.example_rename_prompt": "Renombra el archivo ",
    "chat.placeholder": "Pregunta sobre tus archivos…",
    "chat.send": "Enviar",
    "chat.thinking": "Pensando…",
    "chat.sources": "Fuentes",
    "chat.filters_applied": "Filtros aplicados en el catálogo",
    "chat.open_catalog": "Abrir catálogo",
    "chat.rename_title": "Nombre nuevo propuesto",
    "chat.confirm": "Confirmar",
    "chat.cancel": "Cancelar",
    "chat.renamed": "Renombrado a {name}",
    "chat.rename_cancelled": "Cancelado. No se cambió nada.",
    "chat.move_title": "Mover {name} a otra carpeta",
    "chat.summary_total": "Documentos",
    "chat.summary_dates": "Fechas",
    "chat.summary_sources": "Fuentes principales",
    "chat.show_source": "Ver documentos de {source}",
    "chat.notice_invalid_reply": "Perdón, no entendí eso. Intenta preguntarlo "
        + "de otra forma.",
    "chat.notice_ai_unavailable": "El proveedor de IA no respondió. Revisa "
        + "Configuración > Proveedor de IA e inténtalo de nuevo.",
    "chat.notice_no_documents": "No encontré documentos que coincidan. Prueba "
        + "con otras palabras.",
    "chat.notice_no_filters": "No pude convertir eso en filtros del catálogo. "
        + "Prueba con un tipo, una fuente o un estado.",
    "chat.notice_rename_not_found": "No encontré ese archivo en este "
        + "proyecto. Prueba con su nombre o su fecha.",
    "chat.notice_rename_invalid": "Ese nombre no tiene caracteres válidos. "
        + "Usa letras y números.",
    "chat.notice_rename_same": "El archivo ya tiene ese nombre.",
    "chat.notice_move_unavailable": "Este proyecto ordena los archivos por "
        + "tipo, así que no se mueven entre carpetas.",
    "chat.notice_rename_unavailable": "Este archivo conserva su nombre: el proyecto cataloga en su lugar, u otros programas lo buscan por su nombre.",
    "chat.notice_move_invalid": "Esa carpeta no está en este proyecto. "
        + "Usa una de las carpetas del proyecto.",
    "chat.notice_move_same": "El archivo ya está en esa carpeta.",
    "chat.notice_blocked": "Solo puedo ayudar con los archivos de este "
        + "proyecto. No puedo ayudar con esa solicitud.",
    "chat.notice_out_of_scope": "Solo puedo ayudar con los archivos de este "
        + "proyecto. No puedo ayudar con esa solicitud.",
    "chat.notice_paused": "Volvamos a tus archivos.",
    "chat.notice_too_many": "Demasiados mensajes a la vez. Espera un momento "
        + "e inténtalo de nuevo.",
    "chat.chars_left": "Quedan {n} caracteres",

    // File links: open, preview, show in Finder
    "files.open": "Abrir",
    "files.preview": "Vista previa",
    "files.reveal": "Mostrar en Finder",
    "files.show_in_catalog": "Ver en el catálogo",
    "files.not_found": "No se encontró el archivo. Puede que se haya "
        + "movido o borrado.",
    "time.just_now": "justo ahora",
    "time.minutes": "hace {n} min",
    "time.hour": "hace 1 hora",
    "time.hours": "hace {n} horas",
    "time.yesterday": "ayer",
    "time.days": "hace {n} días",

    // Settings
    "settings.research_name": "Nombre del proyecto",
    "settings.folder": "Selecciona una carpeta o disco",
    "settings.browse": "Buscar carpeta",
    "settings.ai_title": "Proveedor de IA",
    "settings.advanced": "Configuración avanzada",
    "settings.ai_text_title": "Texto e imágenes",
    "settings.ai_fallback_title": "Respaldo (opcional)",
    "settings.ai_fallback_hint": "Responde cuando el proveedor principal "
        + "falla o no puede leer un archivo. Con una clave de Claude "
        + "guardada, Claude es el respaldo a menos que elijas otro.",
    "settings.ai_media_title": "Audio y video",
    "settings.ai_media_hint": "Solo Google Gemini lee audio y video. Las "
        + "claves pagadas de Gemini no se usan para entrenar modelos. Las "
        + "gratuitas sí.",
    "settings.ai_none": "Ninguno",
    "settings.server_title": "Servidor (opcional)",
    "settings.server_hint": "Un servidor de Cataloga que guarda las claves "
        + "de API. Déjalo vacío para llamar a los proveedores desde esta "
        + "computadora.",
    "settings.server_url": "URL del servidor",
    "settings.ai_provider": "Proveedor de IA",
    "settings.api_key": "Clave de API",
    "settings.api_key_placeholder": "Pega tu clave de API",
    "settings.model": "Modelo",
    "settings.save": "Guardar",
    "settings.save_anyway": "Guardar de todos modos",
    "settings.saving": "Guardando...",
    "settings.saved": "Configuración guardada.",
    "settings.load_failed": "No se pudo cargar la configuración: {message}",

    // Drop Zone (not shown on screen yet). "Drop Zone" stays in English
    // because it is the folder's real name on disk.
    // Settings: language. Each language name is in its own language.
    "lang.title": "Idioma",
    "lang.en": "English",
    "lang.es": "Español (Latinoamérica)",

    // Settings: file names
    "naming.title": "Nombres de archivo",
    "naming.m1": "Fecha y tema",
    "naming.m1_example": "fecha_nombre-del-tema.pdf",
    "naming.m2": "Fuente, fecha y tema",
    "naming.m2_example": "nombre-de-la-fuente_fecha_nombre-del-tema.pdf",
    "naming.m3": "Número y tema",
    "naming.m3_example": "0001_nombre-del-tema.pdf",
    "naming.m4": "Tema, fuente y fecha",
    "naming.m4_example": "nombre-del-tema_nombre-de-la-fuente_fecha.pdf",
    "naming.m5": "Evento y año, más un número",
    "naming.m5_example": "Nombre-Del-Evento_1998_1.jpg",
    "naming.custom": "Personalizado",
    "naming.keep": "Conservar los nombres originales",
    "naming.keep_example": "el-nombre-que-le-diste.pdf",
    "naming.preview": "Vista previa",
    "naming.stamp_order": "Fechas impresas en las fotos",
    "naming.stamp_month": "Mes primero (11 13 '97)",
    "naming.stamp_day": "Día primero (13 11 97)",
    "naming.help_names": "Opcional · Sugerido: llenarlo ayuda a que Cataloga nombre tus archivos con más precisión, y Sugerido marca el método que ya siguen tus archivos. Solo cambian los nombres nuevos; los que ya existen se quedan. Se quitan los acentos, una marca de versión como v02 queda al final y la extensión se agrega sola. Un nombre ya usado recibe _2, _3, y un nombre sin fecha confiable no lleva fecha. Con Evento y año, el archivo toma el nombre de su carpeta de evento. La fecha de una foto sale de su sello impreso, luego de la cámara, luego de un año en su nombre o carpeta.",
    "help.open": "Ayuda",
    "help.drop_zone": "Cataloga crea las carpetas ahora y archiva lo que sueltes en la carpeta Drop Zone.",
    "naming.style": "Estilo",
    "naming.blocks_add": "Haz clic en las partes en orden",
    "naming.chosen": "Tu nombre de archivo",
    "naming.chosen_empty": "Todavía no hay partes. Haz clic en Tema, Fuente, "
        + "Fecha u Original.",
    "naming.block_topic": "Tema",
    "naming.block_source": "Fuente",
    "naming.block_date": "Fecha",
    "naming.block_number": "Número",
    "naming.block_original": "Original",
    "naming.separator": "Separador",
    "naming.move_left": "Mover a la izquierda",
    "naming.move_right": "Mover a la derecha",
    "naming.remove_block": "Quitar parte",
    "naming.legacy": "Nombre personalizado guardado: {template}. Haz clic en "
        + "las partes para reemplazarlo.",
    "naming.err_no_blocks": "Haz clic en al menos una parte del nombre.",
    "naming.err_empty": "Escribe una plantilla o elige uno de los 4 métodos.",
    "naming.err_no_token": "Agrega al menos uno de estos: {date}, {source}, "
        + "{topic}, {number}, {topic_number} o {original}.",
    "naming.err_unknown": "{token} no es una parte válida. Usa {date}, "
        + "{source}, {topic}, {number}, {topic_number} o {original}.",
    "naming.err_chars": "Los nombres de archivo no pueden usar estos "
        + "caracteres: / \\ : * ? \" < > |",

    // Settings: categories (Digital Archiving Guideline)
    "categories.title": "Categorías",
    "categories.industry": "Industria",
    "categories.industry_placeholder": "Por ejemplo: documental deportivo",
    "categories.suggest": "Sugerir categorías",
    "categories.suggesting": "Pidiendo categorías al proveedor de IA...",
    "categories.suggested":
        "La lista se reemplazó. Haz clic en Guardar para conservarla.",
    "categories.need_industry": "Primero escribe la industria.",
    "categories.add": "Agregar categoría",
    "categories.remove": "Quitar categoría",
    "categories.name_placeholder": "Categoría",
    "categories.subs_placeholder": "Subcategorías, separadas por comas",
    "sheet.title": "Sobre este proyecto",
    "sheet.placeholder": "Unas líneas sobre el trabajo ayudan a Cataloga a entender tus archivos.",
    "sheet.suggest": "Escríbela por mí",
    "sheet.need_folder": "Elige primero la carpeta del proyecto.",
    "folders.title": "Nombres de carpeta",
    "folders.suggest": "Sugerir carpetas",
    "folders.file_types": "Empezar con tipos de archivo",
    "folders.suggesting": "Pidiendo carpetas a Ollama Cloud...",
    "folders.suggested": "Edita las carpetas y luego crea el proyecto.",
    "folders.reading": "Leyendo lo que hay en la carpeta para proponer sus carpetas...",
    "folders.from_files": "Carpetas para los archivos que ya están en esta carpeta, y solo para ellos. Edítalas y luego crea el proyecto.",
    "folders.from_organized": "Esta carpeta ya está organizada: sus carpetas se quedan como están. Solo aparece una carpeta nueva para archivos sueltos que no encajan en ninguna.",
    "folders.need_description": "Escribe unas líneas en Sobre este proyecto primero.",
    "folders.add": "Agregar carpeta",
    "folders.remove": "Quitar carpeta",
    "folders.remove_with_subs": "¿Quitar \"{name}\" y sus subcarpetas?",
    "folders.has_documents":
        "Hay {n} documentos en esta carpeta, así que se queda.",
    "folders.name_placeholder": "Nombre de la carpeta",
    "folders.inside": "Dentro de",
    "folders.top_level": "Nivel principal",
    "folders.unnamed": "(sin nombre)",
    "folders.err_none": "Agrega al menos una carpeta.",
    "folders.err_empty": "Cada carpeta necesita un nombre.",
    "folders.err_long":
        "\"{name}\" es muy largo. Usa 60 caracteres o menos.",
    "folders.err_chars": "\"{name}\" tiene un carácter que las carpetas no "
        + "pueden usar: / \\ : * ? \" < > |",
    "folders.err_reserved": "\"{name}\" no puede ser nombre de carpeta en "
        + "Mac o Windows.",
    "folders.err_twin":
        "Hay dos carpetas llamadas \"{name}\" en el mismo lugar.",
    "folders.flag_events": "Eventos",
    "folders.flag_events_hint": "Guarda una carpeta por evento, llamada "
        + "Evento_Año. Cataloga puede proponer carpetas de evento aquí.",
    "folders.flag_fallback": "Descarte",
    "folders.flag_fallback_hint": "Los archivos que no encajan en ninguna "
        + "otra carpeta van aquí en vez de a Revisión manual.",
    "folders.flag_leave": "Dejar como está",
    "folders.flag_leave_hint": "Los archivos de esta carpeta se catalogan, "
        + "pero nunca se propone moverlos ni renombrarlos.",
    "folders.flag_auto": "Sin preguntar",
    "folders.flag_auto_hint": "Los archivos nuevos que van aquí se archivan "
        + "sin preguntar (proyectos sin Drop Zone).",
    "folders.numbered": "Numerar carpetas nuevas (01_, 02_)",
    "folders.err_depth": "Las carpetas pueden tener seis niveles como máximo.",
    "folders.err_subs": "Una carpeta puede tener 10 subcarpetas como máximo.",
    "folders.learn": "Aprender de mi carpeta",
    "folders.learning": "Leyendo las carpetas que ya tienes...",
    "folders.learned": "Se aprendieron {n} carpetas de tu carpeta. Edítalas "
        + "y guarda.",
    "folders.need_folder": "Elige una carpeta primero.",
    "folders.has_documents_plan": "{n} archivos están aquí. Si la quitas, "
        + "reciben otra carpeta en Por aprobar.",
    "folders.plan_note": "Los cambios de carpetas esperan en Por aprobar.",
    "folders.catalog_note": "Solo catalogar está activo, así que nada se "
        + "mueve. Estas carpetas se usan cuando lo desactives.",
    "folders.turn_off": "Desactivar Solo catalogar",
    "folders.turn_off_confirm": "¿Desactivar Solo catalogar? Cataloga "
        + "propondrá una carpeta para cada archivo en Por aprobar. Nada se "
        + "mueve hasta que lo apruebes.",
    "folders.turned_off": "Solo catalogar está desactivado. Los movimientos "
        + "esperan en Por aprobar.",
    "folders.no_provider": "Carpetas guardadas. Conecta un proveedor de AI "
        + "para recibir propuestas de movimiento, o mueve los archivos tú "
        + "con Mover a…",
    "folders.open_provider": "Abrir Proveedor de AI",
    "folders.remove_title": "¿Quitar \"{name}\" de las carpetas?",
    "folders.remove_lead": "{n} archivos están en esta carpeta. No se borra "
        + "nada: elige a dónde van.",
    "folders.remove_lead_one": "1 archivo está en esta carpeta. No se borra "
        + "nada: elige a dónde va.",
    "folders.remove_where": "¿A dónde van los archivos?",
    "folders.remove_leave": "Dejarlos donde están",
    "folders.remove_note": "Los movimientos esperan en Por aprobar. La "
        + "carpeta sale del disco solo cuando queda vacía, después de "
        + "aplicar, y Deshacer la devuelve.",
    "folders.remove_confirm": "Quitar carpeta",
    "folders.remove_saved_later": "Guarda para mandar los movimientos a Por "
        + "aprobar.",
    "folders.moves_waiting": "Carpetas guardadas. Los movimientos esperan en "
        + "Por aprobar.",
    "folders.refiling": "Carpetas guardadas. Cataloga está proponiendo una "
        + "carpeta para cada archivo; los movimientos esperan en Por "
        + "aprobar.",

    // Account and login
    "auth.register_title": "Crear una cuenta",
    "auth.register_hint": "Cada cuenta en esta computadora tiene su "
        + "propia lista de proyectos y configuración. Los catálogos se "
        + "quedan dentro de cada carpeta de proyecto. Si olvidas la "
        + "contraseña, la clave de recuperación que recibes después te "
        + "deja poner una nueva.",
    "auth.login_title": "Iniciar sesión",
    "auth.username": "Usuario",
    "auth.password": "Contraseña",
    "auth.confirm_password": "Confirmar contraseña",
    "auth.create_account": "Crear cuenta",
    "auth.log_in": "Iniciar sesión",
    "auth.log_out": "Cerrar sesión",
        "auth.password_mismatch": "Las contraseñas no coinciden",
    "auth.show_password": "Mostrar contraseña",
    "auth.hide_password": "Ocultar contraseña",
    "preview.close": "Cerrar vista previa",
    "preview.unavailable": "Este archivo no se puede ver aquí. Usa Mostrar en "
        + "la carpeta para verlo.",
    "preview.loading": "Cargando…",
    "auth.need_account": "Crear una cuenta",
    "auth.have_account": "Ya tengo una cuenta",
    "auth.forgot": "¿Olvidaste tu contraseña?",
    "account.title": "Cuenta",
    "account.change_password": "Cambiar contraseña",
    "account.current_password": "Contraseña actual",
    "account.new_password": "Contraseña nueva",
    "account.password_changed":
        "Contraseña cambiada. Tu sesión sigue abierta.",

    // Projects (multi-project)
    "header.new_project": "Proyecto nuevo…",
    "header.unavailable": "{name} (no disponible)",
    "header.unavailable_hint": "No se encuentra la carpeta. Ábrelo y "
        + "quítalo en Configuración.",
    "project.edit_title": "Configuración del proyecto",
    "project.new_title": "Proyecto nuevo",
    "project.folder_locked": "La carpeta del proyecto no se puede cambiar, "
        + "porque el catálogo se guarda dentro de ella.",
    "project.create": "Crear proyecto",
    "project.mode_tree": "Usar una Drop Zone",
    "project.catalog_only": "Solo catalogar",
    "project.archive_title": "¿Cuándo debe Cataloga leer esta carpeta?",
    "project.archive_now": "Ahora",
    "project.archive_later": "Después",
    "project.folder_facts": "Esta carpeta tiene {files} archivos en {folders} carpetas ({size}).",
    "project.linked_advice": "Esta carpeta parece una página web o un "
        + "proyecto enlazado ({markers}). Mover o renombrar sus archivos "
        + "lo rompería. Catalog only, que llega pronto, mantendrá todos los "
        + "enlaces funcionando.",
    "project.creating": "Creando el proyecto...",
    "project.created": "Proyecto creado.",
    "project.created_later": "Proyecto creado. Todavía no se ha leído nada: pulsa Archivar ahora en Inicio cuando quieras.",
    "project.opened_existing": "Esta carpeta ya tenía un catálogo de "
        + "Cataloga, así que se agregó a tus proyectos.",
    "project.cancel": "Cancelar",
    "project.remove": "Quitar proyecto",
    "project.remove_title": "¿Quitar \"{name}\" de Cataloga?",
    "project.remove_text": "Esto solo saca el proyecto de tu lista. Su "
        + "carpeta, sus archivos y su catálogo se quedan donde están. "
        + "Puedes volver a agregar la misma carpeta con Proyecto nuevo y "
        + "todo va a estar ahí.",
    "project.remove_confirm": "Quitar",
    "project.removed": "Proyecto quitado de la lista. Su carpeta y sus "
        + "archivos no cambiaron.",
    "catalog.no_project": "Todavía no hay proyecto. Crea uno para ver sus "
        + "archivos aquí.",

    // Labels for values stored in the database. The stored value itself
    // never changes; only what the user sees.
    "value.Press": "Prensa",
    "value.Documents": "Documentos",
    "value.Photos": "Fotos",
    "value.Audio": "Audio",
    "value.Video": "Video",
    "value.Classified": "Clasificado",
    "value.Manual Review": "Revisión manual",
    "value.Edited": "Editado",
    "value.Renamed": "Renombrado",
    "value.Public": "Público",
    "value.Internal": "Interno",
    "value.Confidential": "Confidencial",
    "value.Restricted": "Restringido",

    // Errors, one per backend error code
    "error.not_found":
        "Ese archivo ya no está en el catálogo. Actualiza la página.",
    "error.invalid_body":
        "La app envió una petición que no se pudo leer. Inténtalo de nuevo.",
    "error.invalid_field": "Ese campo no se puede editar.",
    "error.missing_field": "Completa todos los campos obligatorios.",
    "error.invalid_directory": "Esa carpeta no existe. Elige otra.",
    "error.folder_not_empty": "Esta carpeta ya tiene {n} elementos. "
        + "Cataloga no los va a mover: solo cataloga los archivos que "
        + "pongas en su carpeta Drop Zone. Haz clic en Guardar de todos "
        + "modos para usar esta carpeta.",
    "error.unsupported_provider": "Ese proveedor de IA no es compatible.",
    "error.invalid_role": "Ese rol de proveedor no existe.",
    "error.invalid_server_url": "La URL del servidor debe empezar con "
        + "http:// o https://.",
    "error.unsupported_format": "Solo se puede exportar en CSV.",
    "error.keyring_failed": "No se pudo guardar la clave de API en el "
        + "Llavero de macOS. Abre Acceso a Llaveros, revisa que el llavero "
        + "de inicio de sesión esté desbloqueado y vuelve a intentarlo.",
    "error.connection_failed": "No se pudo conectar con el proveedor de IA. "
        + "Revisa la clave de API y el modelo.",
    "error.no_project":
        "No hay ningún proyecto abierto. Crea uno en Configuración.",
    "error.project_unavailable": "La carpeta del proyecto {path} no está "
        + "disponible. Conecta el disco o elige otro proyecto.",
    "error.project_exists":
        "Esa carpeta ya es un proyecto. Elígela en la lista de proyectos.",
    "error.unauthorized": "Inicia sesión para usar Cataloga.",
    "error.wrong_login": "El usuario o la contraseña no son correctos.",
    "error.wrong_password": "La contraseña actual no es correcta.",
    "error.too_many_attempts": "Demasiados intentos fallidos. Prueba otra vez "
        + "en {seconds} segundos.",
    "error.password_too_short":
        "La contraseña debe tener al menos 8 caracteres.",
    "error.password_too_long": "La contraseña es demasiado larga. Usa 72 "
        + "caracteres o menos (menos si tiene acentos o símbolos).",
    "error.username_taken": "Ese usuario ya existe.",
    "error.invalid_username": "Usa de 3 a 30 letras, números, puntos, "
        + "guiones bajos o guiones.",
    "error.generic": "Algo salió mal. Inténtalo de nuevo.",
    "error.invalid_name": "El nombre nuevo no tiene caracteres válidos.",
    "error.file_missing": "El archivo no está o está fuera de la carpeta del "
        + "proyecto.",
    "error.invalid_categories": "La lista de categorías no es válida. Revisa "
        + "los nombres y deja 10 categorías o menos.",
    "error.suggest_failed":
        "El proveedor de IA no sugirió categorías. Inténtalo de nuevo.",
    "error.no_provider": "Primero elige un proveedor de IA en Configuración.",
    "error.nothing_to_learn": "Esta carpeta no tiene subcarpetas de las "
        + "que aprender.",
    "error.invalid_folders":
        "El árbol de carpetas no es válido. Revisa los nombres.",
    "error.invalid_folder_moves": "Una carpeta elegida para los "
        + "archivos no está en el árbol. Elige otra.",
    "error.invalid_sheet": "La ficha del proyecto es demasiado larga. Usa "
        + "1,500 caracteres o menos.",
    "error.invalid_description":
        "La descripción debe tener 300 caracteres o menos.",
    "error.folder_not_empty": "No se puede quitar una carpeta con documentos.",
    "error.unknown_folder": "Esa carpeta no está en este proyecto.",
    "error.not_tree_project":
        "Este proyecto ordena los archivos por tipo, así que no se mueven.",
    "error.use_move": "Usa Mover para cambiar la carpeta de un documento.",
    "error.catalog_only": "Este proyecto cataloga los archivos en su lugar: "
        + "nada se mueve ni se renombra.",
    "error.protected_name": "Otros programas buscan este archivo por su "
        + "nombre, así que lo conserva.",
    "error.no_api_key": "Ollama Cloud todavía no tiene API key. Agrégala en "
        + "Configuración avanzada, o arma las carpetas a mano.",
    "error.suggest_folders_failed":
        "El proveedor de IA no sugirió carpetas. Inténtalo de nuevo.",
    "settings.tab_project": "Proyecto",
    "settings.tab_general": "General",
    "settings.change": "Cambiar",
    "settings.done": "Listo",
    "settings.optional": "Opcional · Sugerido",
    "settings.suggested": "Sugerido",
    "settings.saved_short": "Guardado",
    "settings.ai_checking": "Revisando la conexión...",
    "settings.ai_connected": "Conectado",
    "settings.ai_no_key": "No hay clave guardada",
    "settings.ai_error": "No se puede conectar",
    "settings.ai_add_key": "Agregar una clave",
    "settings.legacy_key_question": "Una clave de {provider} se guardó en esta Mac antes de que cada cuenta tuviera las suyas. ¿Es tuya?",
    "settings.legacy_key_claim": "Usarla en mi cuenta",
    "settings.legacy_key_own": "Agregar mi propia clave",
    "error.legacy_key_gone": "Esa clave ya no está disponible. Otra cuenta se la quedó. Agrega tu propia clave.",
    "sheet.writing": "Cataloga está escribiendo…",
    "sheet.again": "Escríbela otra vez",
    "folders.none_yet": "Todavía no hay carpetas",
    "folders.count_one": "1 carpeta",
    "folders.count": "{n} carpetas",
    "account.save_password": "Guardar la contraseña nueva",
    "project.remove_heading": "Quitar proyecto",
    "dash.media_mix": "Mezcla de medios",
    "dash.mix_open": "{type}: {n}. Verlos en la lista del Catálogo",
    "help.language": "Cambia los botones, etiquetas y mensajes de la app. Los nombres de archivo y los resúmenes no se traducen.",
    "help.archive": "Ahora lee la carpeta enseguida y propone sus carpetas y nombres. Después solo la lista: nada va a la IA hasta que pulses Archivar ahora en Inicio. Solo catalogar lee cada archivo donde está y nunca mueve ni renombra nada.",
    "help.folders": "Opcional · Sugerido: llenarlo ayuda a que Cataloga clasifique tus archivos con más precisión. Con Ahora, Cataloga propone carpetas solo para los archivos que ya están en la carpeta. Hasta 6 niveles, 20 carpetas principales y 10 subcarpetas en cada una. Las carpetas ya creadas no se renombran, y una carpeta que quitas se queda en el disco. Un cambio que mueva archivos espera en Por aprobar.",
    "categories.hint": "Cataloga clasifica cada documento nuevo en una de estas categorías. Escribe tu industria y haz clic en Sugerir categorías; después edita la lista. Hasta 10 categorías. Un documento que no encaje en ninguna va a Revisión manual. Los documentos conservan su categoría si cambias la lista.",
    "sheet.later": "Cataloga lo escribirá cuando lea la carpeta.",
    "folders.later": "Las carpetas se proponen cuando Cataloga lea la carpeta.",
    "error.sheet_failed": "Cataloga no pudo escribir la descripción. Inténtalo otra vez o escríbela tú.",
    "value.Moved": "Movido",
    "value.Undone": "Deshecho",
    "plan.select_all": "Seleccionar todo",
    "settings.key_saved_line": "Hay una clave guardada.",
    "settings.api_key_replace": "Pega una clave nueva para reemplazarla",
    "settings.need_folder": "Escoge una carpeta primero.",
    "settings.need_name": "Escribe un nombre para el proyecto.",
    "plan.need_approval": "Aprueba al menos un cambio.",
    "catalog.filter_source_one": "Fuente: {source}",
    "plan.summary_moves": "{n} movimientos",
    "plan.summary_removal_one": "1 carpeta se quita si queda vacía",
    "plan.summary_removals": "{n} carpetas se quitan si quedan vacías",
    "plan.summary_renames": "{n} renombres",
    "settings.wait_line": "Aparecen cuando eliges una carpeta.",
    "catalog.empty_place": "Todavía no hay actividad. Pulsa Archivar ahora en Inicio.",

    // Calm frame, first way in, accounts (Nov 9)
    "delete.open": "Borrar cuenta",
    "delete.title": "¿Borrar tu cuenta?",
    "delete.lead": "Esto borra de esta Mac:",
    "delete.goes_account": "tu cuenta y tu contraseña;",
    "delete.goes_recovery": "tu recovery key;",
    "delete.goes_keys": "tus API keys guardadas;",
    "delete.goes_settings": "tus ajustes y la lista de proyectos de esta "
        + "cuenta.",
    "delete.stays": "Tus archivos y carpetas de proyectos se quedan donde "
        + "están.",
    "delete.catalogs": "Cada proyecto conserva su carpeta de catálogo "
        + ".cataloga. Bórrala a mano si también quieres quitarla.",
    "delete.password": "Escribe tu contraseña para confirmar",
    "delete.confirm": "Borrar cuenta",
    "legal.title": "Legal",
    "legal.terms": "Términos y condiciones",
    "legal.privacy": "Política de privacidad",
    "legal.version": "Cataloga 1.0",
    "legal.close": "Cerrar",
    "terms.title": "Antes de crear tu cuenta",
    "terms.title_update": "Los términos cambiaron",
    "terms.lead": "Lee los puntos clave. El texto completo está en los enlaces "
        + "de abajo.",
    "terms.point_local": "Cataloga funciona en tu Mac. Tus archivos se quedan "
        + "en tu computadora.",
    "terms.point_approve": "Nada se mueve ni se renombra hasta que lo "
        + "apruebes. Los originales nunca cambian.",
    "terms.point_ai": "Para leer tus archivos, su contenido se envía al "
        + "proveedor de IA que escojas. La IA puede equivocarse: revisa los "
        + "resultados.",
    "terms.point_as_is": "Cataloga se ofrece \"tal cual\". Guarda tu propia "
        + "copia. El desarrollador no responde por datos perdidos, hackeos "
        + "ni filtraciones.",
    "terms.read_terms": "Leer Términos y condiciones",
    "terms.read_privacy": "Leer Política de privacidad",
    "terms.agree": "Leí y acepto los Términos y condiciones y la Política de "
        + "privacidad.",
    "terms.no_recovery": "Si pierdes la contraseña y la clave de recuperación, "
        + "la cuenta no se puede recuperar.",
    "terms.accept_new": "Aceptar y crear cuenta",
    "terms.accept_update": "Aceptar y continuar",
    "terms.button_hint": "El botón se activa cuando marcas la casilla.",
    "recovery.title": "Tu clave de recuperación",
    "recovery.lead": "Si olvidas la contraseña, esta clave te deja poner una "
        + "nueva. Guárdala en un lugar seguro, fuera de las carpetas de tus "
        + "proyectos.",
    "recovery.copy": "Copiar",
    "recovery.copied": "Copiada.",
    "recovery.copy_failed": "No se pudo copiar. Selecciona la clave y cópiala.",
    "recovery.save_now": "Guardar ahora",
    "recovery.later": "Después",
    "recovery.way_save": "Guardar ahora abre la ventana de Guardar con el "
        + "archivo listo: {file} en Documentos.",
    "recovery.way_later": "Después: puedes guardarla cuando quieras en "
        + "Configuración › Cuenta.",
    "recovery.no_window": "La ventana de Guardar solo se abre en la app de "
        + "Cataloga. Copia la clave.",
    "recovery.row_label": "Clave de recuperación",
    "recovery.not_saved": "Todavía no está guardada. Guárdala para poder "
        + "cambiar tu contraseña.",
    "recovery.saved_on": "Guardada el {date}.",
    "recovery.save_current": "Guardar la clave actual",
    "recovery.get_new": "Crear una clave nueva",
    "recovery.type_password": "Escribe tu contraseña para seguir",
    "recovery.continue": "Seguir",
    "forgot.title": "Cambia tu contraseña",
    "forgot.lead": "Usa la clave de recuperación que guardaste al crear la "
        + "cuenta.",
    "forgot.key": "Clave de recuperación",
    "forgot.reset": "Cambiar contraseña",
    "forgot.after": "Después del cambio recibes una clave nueva, y la anterior "
        + "deja de servir.",
    "forgot.back": "Volver a entrar",
    "error.wrong_recovery": "El usuario o la clave de recuperación no son "
        + "correctos.",
    "error.terms_not_accepted": "Primero acepta los Términos y la Política de "
        + "privacidad.",
    "error.inside_project": "Escoge una carpeta fuera de tus proyectos para la "
        + "clave.",
    "error.ticket_expired": "Escribe tu contraseña para guardar la clave.",
    "error.no_key": "No hay clave de recuperación. Crea una clave nueva.",
    "error.outside_project": "Ese archivo está fuera de la carpeta del "
        + "proyecto.",
    "settings.autosave": "Los cambios se guardan solos.",
    "project.optional": "Detalles opcionales",
    "start.title": "Escoge una carpeta para empezar",
    "start.lead": "Cataloga la lee y propone nombres y carpetas. Nada se mueve "
        + "hasta que apruebes.",
    "start.choose": "Escoger carpeta",
    "start.step_1": "Paso 1",
    "start.step_1_name": "Escoge una carpeta",
    "start.step_1_text": "Tus archivos se quedan donde están.",
    "start.step_2": "Paso 2",
    "start.step_2_name": "Léela ahora o después",
    "start.step_2_text": "Cataloga describe cada archivo.",
    "start.step_3": "Paso 3",
    "start.step_3_name": "Aprueba los cambios",
    "start.step_3_text": "Tú decides cada nombre y cada movimiento.",
    "dash.no_project": "Todavía no hay proyecto. Crea uno para ver tus números "
        + "aquí.",
    "dash.review_one": "archivo necesita revisión",
    "dash.review_many": "archivos necesitan revisión",
    "dash.nothing_review": "Nada que revisar",
    "dash.all_classified": "Todo está clasificado.",
    "dash.sources_count": "Fuentes registradas · {n}",
    "plan.no_project": "Todavía no hay proyecto. Crea uno para ver aquí los "
        + "cambios por aprobar.",
    "plan.show": "Mostrar",
    "plan.show_all": "Todos {n}",
    "plan.show_rename": "Renombres {n}",
    "plan.show_move": "Movimientos {n}",
    "plan.show_skipped": "Saltados {n}",
    "plan.files_one": "1 archivo",
    "plan.files_many": "{n} archivos",
    "plan.new_folder": "carpeta nueva",
    "plan.approve_row": "Aprobar {name}",
    "plan.in_folder": "en {folder}",
    "plan.skip": "Saltar",
    "plan.undo_skip": "Deshacer",
    "plan.skipped_note": "Saltado: se queda como está",
    "plan.summary_changes": "{n} cambios",
    "plan.summary_note": "Nada cambia hasta que apliques.",
    "plan.leave_note": "Los archivos de una carpeta marcada Dejar como está se "
        + "catalogan, pero nunca se mueven ni se renombran.",
    "plan.tab_changes": "Cambios",
    "catalog.download_label": "Descargar la hoja",
    "catalog.showing": "Mostrando {n} de {total} archivos",
    "catalog.pages": "Páginas",
    "catalog.page_prev": "Anterior",
    "catalog.page_next": "Siguiente",
    "catalog.page_of": "Página {n} de {total}",
    "preview.previous": "Archivo anterior",
    "preview.next": "Archivo siguiente",
    "preview.new_name": "Nombre nuevo (por aprobar)",
    "preview.where": "Dónde está",
    "preview.reveal_hint": "Muestra el archivo en su carpeta. Nada se mueve.",
    "preview.keys": "Espacio o Esc para cerrar · ← → siguiente archivo",
    "preview.count": "{n} de {total}",
    "chat.limits": "Pregúntale a Cataloga solo responde sobre los archivos de "
        + "este proyecto.",
};
