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
    "catalog.search": "Buscar",
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
    "catalog.edit_mode_on": "El modo edición está activo. Haz clic en una "
        + "celda para editarla. La actualización automática está en pausa.",
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

    // Dashboard
    "dash.classified": "Documentos clasificados",
    "dash.review": "Necesitan revisión manual",
    "dash.sources": "Fuentes registradas",
    "dash.breakdown": "Desglose por tipo de medio",
    "dash.activity": "Actividad reciente",
    "dash.empty": "Todavía no hay actividad. Pon archivos en la Drop Zone "
        + "para empezar.",
    "dash.load_failed": "No se pudo cargar el panel: {message}",
    "dash.of_total": "de {n} documentos",
    "dash.no_documents": "Todavía no hay documentos",

    // Chat
    "chat.open": "Pregunta a Cataloga",
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
    "naming.custom": "Personalizado",
    "naming.template": "Plantilla",
    "naming.template_help":
        "Usa {date}, {source}, {topic}, {number} y {original}.",
    "naming.preview": "Vista previa",
    "naming.media_rule": "Las fotos, el audio y el video usan la fecha del "
        + "archivo y un número, por ejemplo 2026-07-15_0001.jpg.",
    "naming.duplicate_rule":
        "Si el nombre ya existe, Cataloga agrega -2, -3 y así.",
    "naming.changed_note": "Solo los archivos nuevos usarán este método.",
    "naming.err_empty": "Escribe una plantilla o elige uno de los 3 métodos.",
    "naming.err_no_token": "Agrega al menos uno de estos: {date}, {source}, "
        + "{topic}, {number} o {original}.",
    "naming.err_unknown": "{token} no es una parte válida. Usa {date}, "
        + "{source}, {topic}, {number} o {original}.",
    "naming.err_chars": "Los nombres de archivo no pueden usar estos "
        + "caracteres: / \\ : * ? \" < > |",

    // Account and login
    "auth.setup_title": "Crea tu cuenta",
    "auth.setup_hint": "Esta cuenta protege Cataloga en esta computadora. "
        + "No cifra tus archivos. Guarda la contraseña en un lugar "
        + "seguro: no hay forma de recuperarla.",
    "auth.login_title": "Iniciar sesión",
    "auth.username": "Usuario",
    "auth.password": "Contraseña",
    "auth.confirm_password": "Confirmar contraseña",
    "auth.create_account": "Crear cuenta",
    "auth.log_in": "Iniciar sesión",
    "auth.log_out": "Cerrar sesión",
    "auth.password_mismatch": "Las contraseñas no coinciden.",
    "account.title": "Cuenta",
    "account.hint": "Una sola cuenta para toda la app y todos los proyectos.",
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
    "error.account_exists": "La cuenta ya existe. Inicia sesión.",
    "error.no_account": "Primero crea la cuenta.",
    "error.generic": "Algo salió mal. Inténtalo de nuevo.",
    "error.invalid_name": "El nombre nuevo no tiene caracteres válidos.",
    "error.file_missing": "El archivo no está o está fuera de la carpeta del "
        + "proyecto.",
};
