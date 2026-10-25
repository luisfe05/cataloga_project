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
    "catalog.no_folder": "Ve a Configuración para elegir la carpeta del "
        + "proyecto y el proveedor de IA.",
    "catalog.empty": "Pon archivos en la carpeta Drop Zone dentro de "
        + "{path}. Aparecerán aquí cuando se clasifiquen.",
    "catalog.no_match": "Ningún archivo coincide con tu búsqueda.",
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
    "dash.action_classified": "Clasificado",
    "dash.action_review": "Marcado para revisión manual,",
    "dash.action_edited": "Editado",
    "dash.empty": "Todavía no hay actividad. Pon archivos en la Drop Zone "
        + "para empezar.",
    "dash.load_failed": "No se pudo cargar el panel: {message}",
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
    "settings.ai_hint": "Conecta tu propia clave de API de IA.",
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
    "error.connection_failed": "No se pudo conectar con el proveedor de IA. "
        + "Revisa la clave de API y el modelo.",
    "error.generic": "Algo salió mal. Inténtalo de nuevo.",
};
