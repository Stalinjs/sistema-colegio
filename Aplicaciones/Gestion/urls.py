from django.urls import path
from . import views
from . import views_reportes as vr

urlpatterns = [
    path("", views.inicio),
    # LOGIN
    path("login/", views.login_view, name="login"),
    path("login/validar/", views.login_validar, name="login_validar"),
    path("logout/", views.logout_view, name="logout"),

    # Recuperar contraseña
    path("password/recuperar/", views.recuperar_password, name="recuperar_password"),
    path("password/cambiar/", views.cambiar_password, name="cambiar_password"),
    
    # DASHBOARDS POR ROL
    path("dashboard_admin/", views.dashboard_admin, name="dashboard_admin"),
    path("dashboard_secretaria/", views.dashboard_secretaria, name="dashboard_secretaria"),
    path("dashboard_docente/", views.dashboard_docente, name="dashboard_docente"),

    # PERFIL DE USUARIOS
    path("mi_perfil/", views.mi_perfil, name="mi_perfil"),
    path("mi_perfil/cambiar_password/", views.cambiar_password_perfil, name="cambiar_password_perfil"),


    # CRUD USUARIOS (ADMIN)
    path("usuarios_lista/", views.usuarios_lista, name="usuarios_lista"),
    path("usuarios_crear/", views.usuarios_crear, name="usuarios_crear"),
    path('editar_usuario/<int:usuario_id>/', views.editar_usuario, name='editar_usuario'),
    path('activar_usuario/<int:usuario_id>/', views.activar_usuario, name='activar_usuario'),
    path('desactivar_usuario/<int:usuario_id>/', views.desactivar_usuario, name='desactivar_usuario'),

    # CRUD SUCURSALES (ADMIN)
    path("sucursales_lista/", views.sucursales_lista, name="sucursales_lista"),
    path("sucursales_crear/", views.sucursales_crear, name="sucursales_crear"),
    path("sucursales_editar/<int:sucursal_id>/", views.sucursales_editar, name="sucursales_editar"),
    path("sucursales_activar/<int:sucursal_id>/", views.sucursales_activar, name="sucursales_activar"),
    path("sucursales_desactivar/<int:sucursal_id>/", views.sucursales_desactivar, name="sucursales_desactivar"),

    # CRUD ESPECIALIDADES (ADMIN)
    path("especialidades_lista/", views.especialidades_lista, name="especialidades_lista"),
    path("especialidades_crear/", views.especialidades_crear, name="especialidades_crear"),
    path("especialidades_editar/<int:esp_id>/", views.especialidades_editar, name="especialidades_editar"),
    path("especialidades_activar/<int:esp_id>/", views.especialidades_activar, name="especialidades_activar"),
    path("especialidades_desactivar/<int:esp_id>/", views.especialidades_desactivar, name="especialidades_desactivar"),

    # CURSOS
    path("cursos_lista/", views.cursos_lista, name="cursos_lista"),
    path("cursos_crear/", views.cursos_crear, name="cursos_crear"),
    path("cursos_editar/<int:curso_id>/", views.cursos_editar, name="cursos_editar"),

    # PARALELOS
    path("paralelos_lista/", views.paralelos_lista, name="paralelos_lista"),
    path("paralelos_crear/", views.paralelos_crear, name="paralelos_crear"),
    path("paralelos_editar/<int:paralelo_id>/", views.paralelos_editar, name="paralelos_editar"),

    # AÑO LECTIVO
    path("anios_lista/", views.anios_lista, name="anios_lista"),
    path("anios_crear/", views.anios_crear, name="anios_crear"),
    path("anios_editar/<int:anio_id>/", views.anios_editar, name="anios_editar"),
    path("anios_activar/<int:anio_id>/", views.anios_activar, name="anios_activar"),

    # ASIGNATURAS
    path("asignaturas_lista/", views.asignaturas_lista, name="asignaturas_lista"),
    path("asignaturas_crear/", views.asignaturas_crear, name="asignaturas_crear"),
    path("asignaturas_editar/<int:asignatura_id>/", views.asignaturas_editar, name="asignaturas_editar"),

    # DOCENTE ASIGNACIÓN
    path("docente_asignacion_lista/", views.docente_asignacion_lista, name="docente_asignacion_lista"),
    path("docente_asignacion_crear/", views.docente_asignacion_crear, name="docente_asignacion_crear"),

    # DOCENTE
    path("mis_cursos/", views.mis_cursos, name="mis_cursos"),
    # DOCENTE - Estudiantes matriculados - Registarr notas
    path("mis_cursos/<int:asignacion_id>/notas/", views.mis_cursos_notas, name="mis_cursos_notas"),

    # ESTUDIANTES
    path("estudiantes_lista/", views.estudiantes_lista, name="estudiantes_lista"),
    path("estudiantes_crear/", views.estudiantes_crear, name="estudiantes_crear"),
    path("estudiantes_editar/<int:estudiante_id>/", views.estudiantes_editar, name="estudiantes_editar"),

    # MATRICULAS
    path("matriculas_lista/", views.matriculas_lista, name="matriculas_lista"),
    path("matriculas_crear/", views.matriculas_crear, name="matriculas_crear"),
    path("matriculas_editar/<int:matricula_id>/", views.matriculas_editar, name="matriculas_editar"),
    
    #REPORTES
    # REPORTES
    path("reportes/promocion/", vr.promocion_buscar, name="promocion_buscar"),
    # Desde matrícula (notas)
    path("reportes/promocion/matricula/<int:matricula_id>/", vr.promocion_certificado, name="promocion_certificado"),
    # Desde promoción histórica
    path("reportes/promocion/historico/<int:promocion_id>/", vr.promocion_certificado_historico, name="promocion_certificado_historico"),

    # REPORTE DE NOTA
    path("reportes/nomina/<int:asignacion_id>/", vr.nomina_notas_print, name="nomina_notas_print"),
    # PROMOCION HISTORICO
    path("promociones/", views.promociones_lista, name="promociones_lista"),
    path("promociones/crear/", views.promociones_crear, name="promociones_crear"),
    path("promociones/<int:promocion_id>/editar/", views.promociones_editar, name="promociones_editar"),


    # SECRETARIA - PERIODOS Y PERMISOS
    path("secretaria/periodos-notas/", views.periodos_notas_config, name="periodos_notas_config"),
    path("secretaria/permisos-notas/", views.permisos_edicion_lista, name="permisos_edicion_lista"),
    path("secretaria/permisos-notas/nuevo/", views.permisos_edicion_crear, name="permisos_edicion_crear"),
    path("secretaria/permisos-notas/<int:permiso_id>/anular/", views.permisos_edicion_anular, name="permisos_edicion_anular"),

]


