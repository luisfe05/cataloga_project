/**
 * lang/es.js
 *
 * Spanish (Latin America, es-419) text for every label, button, and
 * message in the app. Must have the same keys as en.js.
 * Words in braces, like {n} or {path}, are filled in by t() in i18n.js.
 */

const LANG_ES = {
    // Navigation and header
    "nav.catalog": "Catálogo",
    "nav.dashboard": "Panel",
    "nav.settings": "Configuración",
    "header.project": "Proyecto",
    "header.no_project": "Todavía no hay proyecto",

    // Catalog
    "catalog.tab_all": "Todos los archivos",
    "catalog.tab_review": "Revisión manual ({n})",
    "catalog.search": "Buscar en el catálogo",
    "catalog.filter_type_all": "Tipo de medio: todos",
    "catalog.filter_source_all": "Fuente: todas",
    "catalog.download": "Descargar hoja de cálculo",
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
    "catalog.save_failed": "No se pudo guardar.",
    "catalog.edit_banner": "Editando. Haz clic en una celda para cambiarla. "
        + "Se guarda al salir de la celda o al presionar Enter. La "
        + "actualización automática está en pausa.",
    "catalog.summary_limit": "El resumen puede tener hasta 100 caracteres.",
    "catalog.summary_count": "{n} / 100",
    "catalog.old_inbox_warning": "Tu carpeta Inbox vieja todavía tiene "
        + "archivos. Muévelos a la Drop Zone para catalogarlos.",
    "catalog.no_folder": "Ve a Configuración para elegir el proveedor de IA.",
    "catalog.empty": "Pon archivos en la carpeta Drop Zone dentro de "
        + "{path}. Aparecerán aquí cuando se clasifiquen.",
    "catalog.no_match": "Ningún archivo coincide con tu búsqueda.",
    "catalog.progress": "Progreso del catálogo",
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
    "catalog.not_in_list": "{value} (no está en la lista)",
    "catalog.note_duplicate": "Duplicado de {name}",
    "catalog.note_no_category": "La categoría no está en la lista del proyecto",
    "catalog.note_no_folder": "Ninguna carpeta encaja con este archivo",
    "catalog.col_folder": "Carpeta",
    "catalog.filter_folder_all": "Carpeta: todas",
    "catalog.filter_subfolder_all": "Subcarpeta: todas",
    "catalog.in_drop_zone": "Drop Zone",
    "catalog.suggested_folder": "Sugerida: {folder}",
    "catalog.create_and_move": "Crear carpeta y mover",
    "catalog.move_to": "Mover a…",
    "catalog.moving": "Moviendo...",
    "catalog.moved": "Movido a {folder}",
    "catalog.note_media": "La lectura de audio y video llega pronto",
    "catalog.note_media_length":
        "La lectura de audio y video llega pronto. Duración {length}",
    "catalog.note_image": "No se pudo leer la imagen",
    "catalog.note_scan": "No se pudieron leer las páginas escaneadas",
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
    "dash.review": "Necesitan revisión manual",
    "dash.sources": "Fuentes registradas",
    "dash.breakdown": "Desglose por tipo de medio",
    "dash.activity": "Actividad reciente",
    "dash.empty": "Todavía no hay actividad. Pon archivos en la Drop Zone "
        + "para empezar.",
    "dash.finding_review_one": "1 documento necesita revisión manual.",
    "dash.finding_review": "{n} documentos necesitan revisión manual.",
    "dash.finding_done": "Todos los documentos están clasificados.",
    "dash.review_button": "Revisar en Catálogo",
    "dash.load_failed": "No se pudo cargar el panel: {message}",
    "dash.of_total": "de {n} documentos",
    "dash.no_documents": "Todavía no hay documentos",

    // Chat
    "chat.open_label": "Abrir el asistente de Cataloga",
    "chat.title": "Asistente de Cataloga",
    "chat.close": "Cerrar",
    "chat.empty_title": "¿En qué te ayudo con este proyecto?",
    "chat.empty_hint": "Puedo buscar archivos, filtrar el catálogo, resumir "
        + "el proyecto y proponer nombres nuevos. Nunca renombro un archivo "
        + "sin tu confirmación.",
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
    "chat.notice_move_invalid": "Esa carpeta no está en este proyecto. "
        + "Usa una de las carpetas del proyecto.",
    "chat.notice_move_same": "El archivo ya está en esa carpeta.",

    // File links: open, preview, show in Finder
    "files.open": "Abrir archivo",
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
    "settings.research_title": "Configuración de la investigación",
    "settings.research_hint": "Configura tu proyecto de investigación y "
        + "dónde se guardan los archivos. Cataloga crea una carpeta Drop "
        + "Zone dentro: pon ahí los archivos nuevos para catalogarlos.",
    "settings.research_name": "Nombre de la investigación",
    "settings.folder": "Carpeta del proyecto",
    "settings.browse": "Buscar carpeta",
    "settings.ai_title": "Proveedor de IA",
    "settings.ai_using": "Cataloga usa {provider} ({model}).",
    "settings.ai_needs_key": "{provider} necesita una clave de API. "
        + "Agrégala en Configuración avanzada.",
    "settings.advanced": "Configuración avanzada",
    "settings.ai_hint": "Elige otro proveedor o modelo de IA. Tu clave "
        + "de API se guarda en el Llavero de macOS.",
    "settings.ai_provider": "Proveedor de IA",
    "settings.api_key": "Clave de API",
    "settings.api_key_placeholder": "Pega tu clave de API",
    "settings.api_key_saved":
        "Guardada. Escribe una clave nueva solo si quieres reemplazarla.",
    "settings.model": "Modelo",
    "settings.save": "Guardar",
    "settings.save_anyway": "Guardar de todos modos",
    "settings.saving": "Guardando y probando la conexión con la IA...",
    "settings.saved":
        "Configuración guardada. La conexión con la IA funciona.",
    "settings.save_failed": "No se pudo guardar la configuración.",
    "settings.load_failed": "No se pudo cargar la configuración: {message}",

    // Drop Zone (not shown on screen yet). "Drop Zone" stays in English
    // because it is the folder's real name on disk.
    "dropzone.title": "Drop Zone",
    "dropzone.instruction": "Copia o arrastra los archivos nuevos a la "
        + "carpeta Drop Zone. Cataloga los procesa y deja tus otros "
        + "archivos donde están.",
    "dropzone.short": "Los archivos nuevos van aquí",

    // Settings: language. Each language name is in its own language.
    "lang.title": "Idioma",
    "lang.hint": "Cambia los botones, etiquetas y mensajes de la app. "
        + "Los nombres de archivo y los resúmenes no se traducen.",
    "lang.en": "English",
    "lang.es": "Español (Latinoamérica)",

    // Settings: file names
    "naming.title": "Nombres de archivo",
    "naming.hint": "Elige cómo Cataloga nombra los archivos nuevos. Los "
        + "archivos que ya están en el catálogo conservan su nombre.",
    "naming.m1": "Fecha y tema",
    "naming.m1_example": "2026-07-15_oceanman-malta.pdf",
    "naming.m2": "Fuente, fecha y tema",
    "naming.m2_example": "el-nuevo-dia_2026-07-15_oceanman-malta.pdf",
    "naming.m3": "Número y tema",
    "naming.m3_example": "0001_oceanman-malta.pdf",
    "naming.m4": "Tema, fuente, fecha y número",
    "naming.m4_example": "oceanman-malta_el-nuevo-dia_2026-07-15_001.pdf",
    "naming.custom": "Personalizado",
    "naming.preview": "Vista previa",
    "naming.media_rule": "Las fotos se nombran con este método según lo "
        + "que muestran, y el audio y el video según el título de sus "
        + "etiquetas. Los archivos sin nada que leer usan su fecha y un "
        + "número, por ejemplo 2026-07-15_0001.jpg, o undated_0001.jpg si "
        + "solo se conoce la fecha del disco.",
    "naming.duplicate_rule":
        "Si el nombre ya existe, Cataloga agrega -2, -3 y así.",
    "naming.changed_note": "Solo los archivos nuevos usarán este método.",
    "naming.blocks_add": "Haz clic en las partes en orden",
    "naming.chosen": "Tu nombre de archivo",
    "naming.chosen_empty": "Todavía no hay partes. Haz clic en Tema, Fuente, "
        + "Fecha, Número u Original.",
    "naming.block_topic": "Tema",
    "naming.block_source": "Fuente",
    "naming.block_date": "Fecha",
    "naming.block_number": "Número",
    "naming.block_original": "Original",
    "naming.separator": "Separador",
    "naming.move_left": "Mover a la izquierda",
    "naming.move_right": "Mover a la derecha",
    "naming.remove_block": "Quitar parte",
    "naming.extension_note": "La extensión (.pdf, .jpg) se agrega sola. "
        + "Número cuenta los archivos con el mismo tema: 001, 002...",
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
    "categories.hint": "Cataloga clasifica cada documento nuevo en una de "
        + "estas categorías. Escribe tu industria y haz clic en Sugerir "
        + "categorías; después edita la lista.",
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
    "categories.rules": "Hasta 10 categorías. Un documento que no encaje en "
        + "ninguna va a Revisión manual. Los documentos conservan su "
        + "categoría si cambias la lista.",

    // Folder tree of a project
    "folders.title": "Carpetas",
    "folders.hint": "Cataloga guarda cada documento nuevo en la carpeta que "
        + "encaja con su contenido. Describe el proyecto y haz clic en "
        + "Sugerir carpetas; luego edita el árbol antes de crear el proyecto.",
    "folders.description": "¿De qué trata este proyecto?",
    "folders.description_placeholder": "Por ejemplo: documental sobre un "
        + "nadador puertorriqueño que compite en Malta",
    "folders.suggest": "Sugerir carpetas",
    "folders.file_types": "Empezar con tipos de archivo",
    "folders.suggesting": "Pidiendo carpetas a Ollama Cloud...",
    "folders.suggested": "Edita las carpetas y luego crea el proyecto.",
    "folders.need_description": "Primero describe el proyecto.",
    "folders.add": "Agregar carpeta",
    "folders.remove": "Quitar carpeta",
    "folders.remove_with_subs": "¿Quitar \"{name}\" y sus subcarpetas?",
    "folders.has_documents":
        "Hay {n} documentos en esta carpeta, así que se queda.",
    "folders.name_placeholder": "Nombre de la carpeta",
    "folders.inside": "Dentro de",
    "folders.top_level": "Nivel principal",
    "folders.unnamed": "(sin nombre)",
    "folders.rules": "Dos niveles como máximo. Hasta 20 carpetas y 10 "
        + "subcarpetas en cada una. Las carpetas ya creadas no se pueden "
        + "renombrar; puedes agregar carpetas y quitar las vacías. Las "
        + "carpetas quitadas se quedan en el disco.",
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
    "folders.err_subs": "Una carpeta puede tener 10 subcarpetas como máximo.",

    // Account and login
    "auth.register_title": "Crear una cuenta",
    "auth.register_hint": "Cada cuenta en esta computadora tiene su propia "
        + "lista de proyectos y sus ajustes. Los catálogos se quedan dentro "
        + "de cada carpeta de proyecto. Una contraseña perdida no se puede "
        + "recuperar.",
    "auth.login_title": "Iniciar sesión",
    "auth.username": "Usuario",
    "auth.password": "Contraseña",
    "auth.confirm_password": "Confirmar contraseña",
    "auth.create_account": "Crear cuenta",
    "auth.log_in": "Iniciar sesión",
    "auth.log_out": "Cerrar sesión",
    "auth.password_mismatch": "Las contraseñas no coinciden.",
    "auth.need_account": "Crear una cuenta",
    "auth.have_account": "Ya tengo una cuenta",
    "auth.forgot": "¿Olvidaste tu contraseña?",
    "auth.forgot_hint": "Las contraseñas no se pueden recuperar: Cataloga "
        + "no usa correo. Tus proyectos y archivos siguen intactos en sus "
        + "carpetas. Crea una cuenta nueva para seguir trabajando.",
    "account.title": "Cuenta",
    "account.hint": "Cada cuenta en esta computadora tiene sus propios "
        + "proyectos y ajustes.",
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
    "project.creating":
        "Creando el proyecto y probando la conexión con la IA...",
    "project.created": "Proyecto creado. La conexión con la IA funciona.",
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
    "catalog.no_project": "Crea un proyecto en Configuración para empezar.",

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
    "error.too_many_attempts": "Demasiadas contraseñas incorrectas. "
        + "Vuelve a intentarlo en {seconds} segundos.",
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
    "error.invalid_folders":
        "El árbol de carpetas no es válido. Revisa los nombres.",
    "error.invalid_description":
        "La descripción debe tener 300 caracteres o menos.",
    "error.folder_not_empty": "No se puede quitar una carpeta con documentos.",
    "error.unknown_folder": "Esa carpeta no está en este proyecto.",
    "error.not_tree_project":
        "Este proyecto ordena los archivos por tipo, así que no se mueven.",
    "error.use_move": "Usa Mover para cambiar la carpeta de un documento.",
    "error.no_api_key": "Ollama Cloud todavía no tiene API key. Agrégala en "
        + "Configuración avanzada, o arma las carpetas a mano.",
    "error.suggest_folders_failed":
        "El proveedor de IA no sugirió carpetas. Inténtalo de nuevo.",
};
