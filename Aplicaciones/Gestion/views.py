from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from django.db.models import Q
from django.contrib.auth.hashers import make_password
from django.contrib.auth.hashers import check_password
from .models import Usuario, Estudiante, Matricula, Paralelo, AnioLectivo, Curso, Sucursal, Nota, Docente, DocenteAsignacion, Especialidad, Asignatura, PeriodoNotas, PermisoEdicionNotas, Promocion, PromocionDetalle
from django.utils import timezone
from django.db import IntegrityError
from django.http import HttpResponseRedirect
from django.urls import reverse
import random
import string
from django.core.mail import send_mail

def inicio(request):
    return render(request, 'inicio.html')
#================================================================= LOGIN ===========================================
def login_view(request):
    return render(request, 'usuarios/login.html')

#  FUNCION PARA VALIDAR LOGIN
def login_validar(request):
    
    if request.method == "POST":
        cedula = (request.POST.get("cedula") or "").strip()
        password = request.POST.get("password")

        try:
            usuario = Usuario.objects.get(cedula=cedula)
        except Usuario.DoesNotExist:
            messages.error(request, "La cédula no está registrada.")
            return redirect("login")
        
        if not usuario.activo:
            messages.error(request, "Tu cuenta está desactivada.")
            return redirect("login")

        # Validar contraseña (hasheada)
        if not check_password(password, usuario.password):
            messages.error(request, "Contraseña incorrecta.")
            return redirect("login")

        # Guardar datos en sesión
        request.session["usuario_id"] = usuario.id
        request.session["usuario_rol"] = usuario.rol
        request.session["usuario_nombre"] = usuario.nombres

        # Redirigir según rol
        if usuario.rol == "admin":
            return redirect("dashboard_admin")

        if usuario.rol == "secretaria":
            return redirect("dashboard_secretaria")

        if usuario.rol == "docente":
            return redirect("dashboard_docente")

    return redirect("login")

# LOGOUT
def logout_view(request):
    request.session.flush()
    return redirect("/")

def recuperar_password(request):
    if request.method == "POST":
        correo = (request.POST.get("correo") or "").strip().lower()

        try:
            usuario = Usuario.objects.get(correo=correo, activo=True)
        except Usuario.DoesNotExist:
            messages.error(request, "No existe un usuario activo con ese correo.")
            return redirect("recuperar_password")

        # Generar contraseña temporal
        nueva_password = ''.join(random.choices(string.digits, k=8))

        usuario.password = make_password(nueva_password)
        usuario.save()

        send_mail(
            subject="Recuperación de contraseña - Sistema Académico",
            message=(
                f"Estimado/a {usuario.nombres},\n\n"
                "Se ha generado una nueva contraseña temporal para su acceso al Sistema Académico "
                "de la Unidad Educativa Monseñor Leónidas Proaño.\n\n"
                f"Usuario: {usuario.cedula}\n"
                f"Nueva contraseña temporal: {nueva_password}\n\n"
                "Le recomendamos ingresar al sistema y solicitar el cambio de contraseña."
            ),
            from_email=None,
            recipient_list=[usuario.correo],
            fail_silently=False,
        )

        messages.success(request, "Se envió una nueva contraseña temporal a su correo.")
        return redirect("login")

    return render(request, "usuarios/recuperar_password.html")


# CAMBIAR CONTRASEÑA (después de validar cédula)
def cambiar_password(request):
    cedula = request.session.get("recuperar_cedula")

    if not cedula:
        messages.error(request, "Primero debes recuperar la contraseña.")
        return redirect("recuperar_password")

    if request.method == "POST":
        nueva_pass = request.POST.get("password")
        confirmar = request.POST.get("password2")

        if nueva_pass != confirmar:
            messages.error(request, "Las contraseñas no coinciden.")
            return redirect("cambiar_password")

        usuario = Usuario.objects.get(cedula=cedula)
        usuario.password = make_password(nueva_pass)
        usuario.save()

        # Limpiar sesión temporal
        del request.session["recuperar_cedula"]

        messages.success(request, "Tu contraseña fue actualizada.")
        return redirect("login")

    return render(request, "usuarios/cambiar_password.html")

# ========================================================================= PAGINA DE INICIO SEGUN EL ROL =====================

# DASHBOARD ADMIN
def dashboard_admin(request):
    if request.session.get("usuario_rol") != "admin":
        return redirect("login")
    return render(request, "dashboard/dashboard_admin.html")

# DASHBOARD SECRETARIA
def dashboard_secretaria(request):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")
    return render(request, "dashboard/dashboard_secretaria.html")

# DASHBOARD DOCENTE
def dashboard_docente(request):
    if request.session.get("usuario_rol") != "docente":
        return redirect("login")
    return render(request, "dashboard/dashboard_docente.html")

# ========================================================================= USUARIOS =====================

# MÓDULO USUARIOS (solo admin)
def usuarios_lista(request):
    if request.session.get("usuario_rol") != "admin":
        return redirect("login")

    estado = request.GET.get("estado", "todos")
    rol = request.GET.get("rol", "todos")

    usuarios = Usuario.objects.all()

    # Filtro por estado
    if estado == "activos":
        usuarios = usuarios.filter(activo=True)
    elif estado == "inactivos":
        usuarios = usuarios.filter(activo=False)

    # Filtro por rol
    if rol != "todos":
        usuarios = usuarios.filter(rol=rol)

    context = {
        "usuarios": usuarios,
        "estado": estado,
        "rol": rol,
    }
    return render(request, "usuarios/usuarios_lista.html", context)

def usuarios_crear(request):
    if request.session.get("usuario_rol") != "admin":
        return redirect("login")
    
    if request.method == "POST":
        cedula = (request.POST.get("cedula") or "").strip()
        nombres = (request.POST.get("nombres") or "").strip()
        apellido_p = (request.POST.get("apellido_paterno") or "").strip()
        apellido_m = (request.POST.get("apellido_materno") or "").strip()
        correo = (request.POST.get("correo") or "").strip()
        telefono = (request.POST.get("telefono") or "").strip()
        direccion = (request.POST.get("direccion") or "").strip()
        rol = (request.POST.get("rol") or "").strip()

        if rol == "admin":
            if Usuario.objects.filter(rol="admin").exists():
                messages.error(request, "Ya existe un Administrador. Solo puede existir uno.")
                return redirect("usuarios_crear")

        if rol == "secretaria":
            if Usuario.objects.filter(rol="secretaria", activo=True).exists():
                messages.error(request, "Ya existe una Secretaría activa. Desactive la actual para registrar otra.")
                return redirect("usuarios_crear")

        # Validaciones básicas
        if Usuario.objects.filter(cedula=cedula).exists():
            messages.error(request, "La cédula ya está registrada.")
            return redirect("usuarios_crear")

        nuevo = Usuario(
            cedula=cedula,
            nombres=nombres,
            apellido_paterno=apellido_p,
            apellido_materno=apellido_m,
            correo=correo if correo else None,
            telefono=telefono if telefono else None,
            direccion=direccion if direccion else None,
            rol=rol,
            password=make_password(cedula)
        )

        try:
            nuevo.save()
        except ValidationError as e:
            msg = e.message_dict.get("cedula", e.messages)
            if isinstance(msg, list):
                msg = " ".join(msg)
            messages.error(request, msg)
            return redirect("usuarios_crear")

        if rol == "docente":
            Docente.objects.create(usuario=nuevo)

        if correo:
            try:
                send_mail(
                    subject="Registro en el Sistema Académico",
                    message=(
                        f"Estimado/a {nuevo.nombres},\n\n"
                        "Usted ha sido registrado en el Sistema Académico de la "
                        "Unidad Educativa Monseñor Leónidas Proaño.\n\n"
                        f"Usuario: {cedula}\n"
                        f"Contraseña inicial: {cedula}\n"
                        f"Rol asignado: {rol}\n\n"
                        "Le recomendamos cambiar su contraseña al ingresar."
                    ),
                    from_email=None,
                    recipient_list=[correo],
                    fail_silently=False,
                )
                messages.success(request, "Usuario creado correctamente y correo enviado.")
            except Exception:
                messages.warning(
                    request,
                    "Usuario creado correctamente, pero no se pudo enviar el correo."
                )
        else:
            messages.success(request, "Usuario creado correctamente.")

        return redirect("usuarios_lista")

    return render(request, "usuarios/usuarios_crear.html")


def activar_usuario(request, usuario_id):
    if request.session.get("usuario_rol") != "admin":
        return redirect("login")

    usuario = get_object_or_404(Usuario, id=usuario_id)

    # Evitar activar una secretaria si ya existe otra activa
    if usuario.rol == "secretaria":
        existe_secretaria_activa = Usuario.objects.filter(
            rol="secretaria",
            activo=True
        ).exclude(id=usuario.id).exists()

        if existe_secretaria_activa:
            messages.error(
                request,
                "Ya existe una Secretaría activa. No se puede activar otra."
            )
            return redirect("usuarios_lista")

    usuario.activo = True
    usuario.save()
    messages.success(request, "Usuario activado correctamente.")
    return redirect("usuarios_lista")


def desactivar_usuario(request, usuario_id):
    if request.session.get("usuario_rol") != "admin":
        return redirect("login")

    usuario = get_object_or_404(Usuario, id=usuario_id)

    # (Opcional) evitar desactivar al único admin
    if usuario.rol == "admin":
        total_admins_activos = Usuario.objects.filter(rol="admin", activo=True).count()
        if total_admins_activos <= 1:
            messages.error(request, "No puedes desactivar al único Administrador activo.")
            return redirect("usuarios_lista")

    usuario.activo = False
    usuario.save()
    messages.success(request, "Usuario desactivado correctamente.")
    return redirect("usuarios_lista")


def editar_usuario(request, usuario_id):
    if request.session.get("usuario_rol") != "admin":
        return redirect("login")
    usuario = get_object_or_404(Usuario, id=usuario_id)

    if request.method == "POST":
        
        usuario.nombres = request.POST.get("nombres")
        usuario.apellido_paterno = request.POST.get("apellido_paterno")
        usuario.apellido_materno = request.POST.get("apellido_materno")
        usuario.correo = request.POST.get("correo")
        usuario.telefono = request.POST.get("telefono")
        usuario.direccion = request.POST.get("direccion")

        rol_nuevo = usuario.rol  
        if usuario.rol != "admin":
            rol_nuevo = request.POST.get("rol")  

        
        if Usuario.objects.exclude(id=usuario_id).filter(cedula=usuario.cedula).exists():
            messages.error(request, "La cédula ya está registrada por otro usuario.")
            return redirect("editar_usuario", usuario_id=usuario.id)

        # VALIDACIÓN: evitar 2 secretarias activas al editar
        if rol_nuevo == "secretaria":
            existe_otra_secretaria_activa = Usuario.objects.filter(
                rol="secretaria",
                activo=True
            ).exclude(id=usuario.id).exists()

            if existe_otra_secretaria_activa:
                messages.error(
                    request,
                    "Ya existe una Secretaría activa. Desactive la actual antes de asignar este rol."
                )
                return redirect("editar_usuario", usuario_id=usuario.id)

        # aplicar el rol ya validado
        usuario.rol = rol_nuevo

        try:
            usuario.save()
        except ValidationError as e:
            msg = e.message_dict.get("cedula", e.messages)
            if isinstance(msg, list):
                msg = " ".join(msg)
            messages.error(request, msg)
            return redirect("editar_usuario", usuario_id=usuario.id)

        # Si ahora es docente y no existe en tabla docente -> crear
        if usuario.rol == "docente" and not hasattr(usuario, "docente"):
            Docente.objects.create(usuario=usuario)

        # Si dejó de ser docente y existe en tabla docente -> eliminar
        if usuario.rol != "docente" and hasattr(usuario, "docente"):
            usuario.docente.delete()

        messages.success(request, "Datos actualizados correctamente.")
        return redirect("usuarios_lista")

    return render(request, "usuarios/usuario_editar.html", {"usuario": usuario})
# ==================================================== Ver datos desde mi perfil ===============================================
# MI PERFIL 
def mi_perfil(request):
    usuario_id = request.session.get("usuario_id")

    if not usuario_id:
        return redirect("login")

    usuario = Usuario.objects.get(id=usuario_id)
    return render(request, "usuarios/mi_perfil.html", {"usuario": usuario})


# CAMBIAR CONTRASEÑA DESDE EL PERFIL
def cambiar_password_perfil(request):
    usuario_id = request.session.get("usuario_id")

    if not usuario_id:
        return redirect("login")

    usuario = Usuario.objects.get(id=usuario_id)

    if request.method == "POST":
        actual = request.POST.get("actual")
        nueva = request.POST.get("nueva")
        confirmar = request.POST.get("confirmar")

        # Validar contraseña actual
        if not check_password(actual, usuario.password):
            messages.error(request, "La contraseña actual es incorrecta.")
            return redirect("cambiar_password_perfil")

        # Validar coincidencia
        if nueva != confirmar:
            messages.error(request, "Las nuevas contraseñas no coinciden.")
            return redirect("cambiar_password_perfil")

        # Guardar nueva contraseña
        usuario.password = make_password(nueva)
        usuario.save()

        messages.success(request, "Tu contraseña ha sido cambiada correctamente.")
        return redirect("mi_perfil")

    return render(request, "usuarios/cambiar_password_perfil.html")

# ========================================================================= SUCURSALES =====================

def sucursales_lista(request):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    estado = request.GET.get("estado", "activas")  # activas | inactivas | todas
    q = request.GET.get("q", "").strip()
    regimen = request.GET.get("regimen", "").strip()

    sucursales = Sucursal.objects.all()

    if estado == "activas":
        sucursales = sucursales.filter(activa=True)
    elif estado == "inactivas":
        sucursales = sucursales.filter(activa=False)

    if q:
        sucursales = sucursales.filter(
            Q(nombre__icontains=q) |
            Q(ubicacion__icontains=q)
        )

    if regimen:
        sucursales = sucursales.filter(ubicacion__iexact=regimen)

    sucursales = sucursales.order_by("nombre")

    context = {
        "sucursales": sucursales,
        "estado": estado,
        "q": q,
        "regimen": regimen,
    }
    return render(request, "sucursales/sucursales_lista.html", context)



def sucursales_crear(request):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        ubicacion = request.POST.get("ubicacion", "").strip()

        if not nombre:
            messages.error(request, "El nombre de la sucursal es obligatorio.")
            return redirect("sucursales_crear")

        if Sucursal.objects.filter(nombre__iexact=nombre).exists():
            messages.error(request, "Ya existe una sucursal con ese nombre.")
            return redirect("sucursales_crear")

        Sucursal.objects.create(
            nombre=nombre,
            ubicacion=ubicacion if ubicacion else None,
            activa=True
        )

        messages.success(request, "Sucursal registrada correctamente.")
        return redirect("sucursales_lista")

    return render(request, "sucursales/sucursales_crear.html")


def sucursales_editar(request, sucursal_id):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    sucursal = get_object_or_404(Sucursal, id=sucursal_id)

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        ubicacion = request.POST.get("ubicacion", "").strip()

        if not nombre:
            messages.error(request, "El nombre de la sucursal es obligatorio.")
            return redirect("sucursales_editar", sucursal_id=sucursal.id)

        if Sucursal.objects.exclude(id=sucursal.id).filter(nombre__iexact=nombre).exists():
            messages.error(request, "Ya existe otra sucursal con ese nombre.")
            return redirect("sucursales_editar", sucursal_id=sucursal.id)

        sucursal.nombre = nombre
        sucursal.ubicacion = ubicacion if ubicacion else None
        sucursal.save()

        messages.success(request, "Sucursal actualizada correctamente.")
        return redirect("sucursales_lista")

    context = {
        "sucursal": sucursal
    }
    return render(request, "sucursales/sucursales_editar.html", context)


def sucursales_activar(request, sucursal_id):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    sucursal = get_object_or_404(Sucursal, id=sucursal_id)
    sucursal.activa = True
    sucursal.save()

    messages.success(request, f"Sucursal '{sucursal.nombre}' activada correctamente.")
    return redirect("sucursales_lista")


def sucursales_desactivar(request, sucursal_id):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    sucursal = get_object_or_404(Sucursal, id=sucursal_id)

    if sucursal.nombre.strip().lower() == "latacunga (matriz)".lower():
        messages.error(request, "No se puede desactivar la sucursal Matriz (Latacunga).")
        return redirect("sucursales_lista")

    sucursal.activa = False
    sucursal.save()

    messages.success(request, f"Sucursal '{sucursal.nombre}' desactivada correctamente.")
    return redirect("sucursales_lista")


# ========================================================================= ESPECIALIDADES =====================
def especialidades_lista(request):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    estado = request.GET.get("estado", "activas")
    q = request.GET.get("q", "").strip()

    especialidades = Especialidad.objects.all()

    if estado == "activas":
        especialidades = especialidades.filter(activa=True)
    elif estado == "inactivas":
        especialidades = especialidades.filter(activa=False)

    if q:
        especialidades = especialidades.filter(
            Q(nombre__icontains=q) |
            Q(descripcion__icontains=q)
        )

    especialidades = especialidades.order_by("nombre")

    context = {
        "especialidades": especialidades,
        "estado": estado,
        "q": q,
    }
    return render(request, "especialidades/especialidades_lista.html", context)


def especialidades_crear(request):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        descripcion = request.POST.get("descripcion", "").strip()

        if not nombre:
            messages.error(request, "El nombre es obligatorio.")
            return redirect("especialidades_crear")

        if Especialidad.objects.filter(nombre__iexact=nombre).exists():
            messages.error(request, "Ya existe una especialidad con ese nombre.")
            return redirect("especialidades_crear")

        Especialidad.objects.create(
            nombre=nombre,
            descripcion=descripcion,
            activa=True
        )

        messages.success(request, "Especialidad registrada correctamente.")
        return redirect("especialidades_lista")

    return render(request, "especialidades/especialidades_crear.html")


def especialidades_editar(request, esp_id):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    especialidad = get_object_or_404(Especialidad, id=esp_id)

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        descripcion = request.POST.get("descripcion", "").strip()

        if not nombre:
            messages.error(request, "El nombre es obligatorio.")
            return redirect("especialidades_editar", esp_id=esp_id)

        if Especialidad.objects.exclude(id=esp_id).filter(nombre__iexact=nombre).exists():
            messages.error(request, "Ya existe otra especialidad con ese nombre.")
            return redirect("especialidades_editar", esp_id=esp_id)

        especialidad.nombre = nombre
        especialidad.descripcion = descripcion
        especialidad.save()

        messages.success(request, "Especialidad actualizada correctamente.")
        return redirect("especialidades_lista")

    context = {
        "especialidad": especialidad
    }
    return render(request, "especialidades/especialidades_editar.html", context)


def especialidades_desactivar(request, esp_id):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    especialidad = get_object_or_404(Especialidad, id=esp_id)
    especialidad.activa = False
    especialidad.save()

    messages.success(request, "Especialidad desactivada correctamente.")
    return redirect("especialidades_lista")

def especialidades_activar(request, esp_id):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    especialidad = get_object_or_404(Especialidad, id=esp_id)
    especialidad.activa = True
    especialidad.save()

    messages.success(request, "Especialidad activada correctamente.")
    return redirect("especialidades_lista")

# ========================================================================= CURSOS =====================


def cursos_lista(request):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    sucursal_id = request.GET.get("sucursal", "").strip()
    nivel = request.GET.get("nivel", "").strip()
    especialidad_id = request.GET.get("especialidad", "").strip()
    q = request.GET.get("q", "").strip()

    if not sucursal_id:
        s_lat = Sucursal.objects.filter(nombre="Latacunga (Matriz)").first()
        if s_lat:
            sucursal_id = str(s_lat.id)

    cursos = Curso.objects.select_related("sucursal", "especialidad").all()

    if sucursal_id:
        cursos = cursos.filter(sucursal_id=sucursal_id)

    if nivel:
        cursos = cursos.filter(nivel=nivel)

    if especialidad_id:
        cursos = cursos.filter(especialidad_id=especialidad_id)

    if q:
        cursos = cursos.filter(
            Q(nombre__icontains=q) |
            Q(sucursal__nombre__icontains=q) |
            Q(especialidad__nombre__icontains=q)
        )

    cursos = cursos.order_by("sucursal__nombre", "nivel", "nombre")

    # combos
    sucursales = Sucursal.objects.filter(activa=True).order_by("nombre")
    especialidades = Especialidad.objects.filter(activa=True).order_by("nombre")

    niveles = [
        ("EGB", "EGB"),
        ("BGU", "BGU"),
        ("BACH_TECNICO", "Bachillerato Técnico"),
    ]

    context = {
        "cursos": cursos,
        "sucursales": sucursales,
        "especialidades": especialidades,
        "niveles": niveles,

        "sucursal_id": sucursal_id,
        "nivel": nivel,
        "especialidad_id": especialidad_id,
        "q": q,
    }
    return render(request, "cursos/cursos_lista.html", context)


def cursos_crear(request):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    sucursales = Sucursal.objects.filter(activa=True).order_by("nombre")
    especialidades = Especialidad.objects.filter(activa=True).order_by("nombre")

    # default: Latacunga (Matriz)
    sucursal_default = Sucursal.objects.filter(nombre="Latacunga (Matriz)").first()

    niveles = [
        ("EGB", "EGB"),
        ("BGU", "BGU"),
        ("BACH_TECNICO", "Bachillerato Técnico"),
    ]

    if request.method == "POST":
        nombre = (request.POST.get("nombre") or "").strip()
        nivel = (request.POST.get("nivel") or "").strip()
        sucursal_id = (request.POST.get("sucursal") or "").strip()
        especialidad_id = (request.POST.get("especialidad") or "").strip() or None
        orden_raw = (request.POST.get("orden") or "").strip()

        if not nombre or not nivel or not sucursal_id:
            messages.error(request, "Nombre, nivel y sucursal son obligatorios.")
            return redirect("cursos_crear")

        if not orden_raw:
            messages.error(request, "El orden es obligatorio (ej: 8, 9, 10...).")
            return redirect("cursos_crear")

        try:
            orden = int(orden_raw)
        except ValueError:
            messages.error(request, "El orden debe ser un número entero.")
            return redirect("cursos_crear")

        if orden < 1 or orden > 20:
            messages.error(request, "El orden debe estar entre 1 y 20.")
            return redirect("cursos_crear")

        sucursal = get_object_or_404(Sucursal, id=sucursal_id)
        especialidad = None
        if especialidad_id:
            especialidad = get_object_or_404(Especialidad, id=especialidad_id)

        if Curso.objects.filter(nombre=nombre, especialidad=especialidad, sucursal=sucursal).exists():
            messages.error(request, "Ese curso ya existe en esa sucursal (y especialidad).")
            return redirect("cursos_crear")

        Curso.objects.create(
            nombre=nombre,
            nivel=nivel,
            sucursal=sucursal,
            especialidad=especialidad,
            orden=orden,   # ✅ guardar orden
        )
        messages.success(request, "Curso creado correctamente.")
        return redirect("cursos_lista")
    context = {
        "sucursales": sucursales,
        "especialidades": especialidades,
        "niveles": niveles,
        "sucursal_default": sucursal_default,
    }
    return render(request, "cursos/cursos_crear.html", context)


def cursos_editar(request, curso_id):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    curso = get_object_or_404(Curso, id=curso_id)
    sucursales = Sucursal.objects.filter(activa=True).order_by("nombre")
    especialidades = Especialidad.objects.filter(activa=True).order_by("nombre")

    niveles = [
        ("EGB", "EGB"),
        ("BGU", "BGU"),
        ("BACH_TECNICO", "Bachillerato Técnico"),
    ]

    if request.method == "POST":
        nombre = (request.POST.get("nombre") or "").strip()
        nivel = (request.POST.get("nivel") or "").strip()
        sucursal_id = (request.POST.get("sucursal") or "").strip()
        especialidad_id = (request.POST.get("especialidad") or "").strip() or None
        orden_raw = (request.POST.get("orden") or "").strip()

        if not nombre or not nivel or not sucursal_id:
            messages.error(request, "Nombre, nivel y sucursal son obligatorios.")
            return redirect("cursos_editar", curso_id=curso.id)

        # ✅ validar orden
        if not orden_raw:
            messages.error(request, "El orden es obligatorio (ej: 8, 9, 10...).")
            return redirect("cursos_editar", curso_id=curso.id)

        try:
            orden = int(orden_raw)
        except ValueError:
            messages.error(request, "El orden debe ser un número entero.")
            return redirect("cursos_editar", curso_id=curso.id)

        if orden < 1 or orden > 20:
            messages.error(request, "El orden debe estar entre 1 y 20.")
            return redirect("cursos_editar", curso_id=curso.id)

        sucursal = get_object_or_404(Sucursal, id=sucursal_id)
        especialidad = None
        if especialidad_id:
            especialidad = get_object_or_404(Especialidad, id=especialidad_id)

        if Curso.objects.exclude(id=curso.id).filter(nombre=nombre, especialidad=especialidad, sucursal=sucursal).exists():
            messages.error(request, "Ya existe un curso igual en esa sucursal (y especialidad).")
            return redirect("cursos_editar", curso_id=curso.id)

        curso.nombre = nombre
        curso.nivel = nivel
        curso.sucursal = sucursal
        curso.especialidad = especialidad
        curso.orden = orden  
        curso.save()

        messages.success(request, "Curso actualizado correctamente.")
        return redirect("cursos_lista")
    return render(request, "cursos/cursos_editar.html", {
        "curso": curso,
        "sucursales": sucursales,
        "especialidades": especialidades,
        "niveles": niveles,
    })

# ========================================================================= PARALELOS =====================

def paralelos_lista(request):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    # filtros GET
    sucursal_id = request.GET.get("sucursal", "").strip()
    curso_id = request.GET.get("curso", "").strip()
    q = request.GET.get("q", "").strip()

    # ✅ Default: Latacunga (Matriz)
    if not sucursal_id:
        s_lat = Sucursal.objects.filter(nombre="Latacunga (Matriz)").first()
        if s_lat:
            sucursal_id = str(s_lat.id)

    paralelos = Paralelo.objects.select_related("curso__sucursal").all()

    if sucursal_id:
        paralelos = paralelos.filter(curso__sucursal_id=sucursal_id)

    if curso_id:
        paralelos = paralelos.filter(curso_id=curso_id)

    if q:
        paralelos = paralelos.filter(
            Q(nombre__icontains=q) |
            Q(curso__nombre__icontains=q) |
            Q(curso__sucursal__nombre__icontains=q)
        )

    paralelos = paralelos.order_by(
        "curso__sucursal__nombre",
        "curso__nombre",
        "nombre"
    )

    # combos (para filtros)
    sucursales = Sucursal.objects.filter(activa=True).order_by("nombre")
    cursos = Curso.objects.select_related("sucursal").all().order_by("sucursal__nombre", "nombre")

    # si hay sucursal elegida, mostrar solo cursos de esa sucursal
    if sucursal_id:
        cursos = cursos.filter(sucursal_id=sucursal_id)

    context = {
        "paralelos": paralelos,
        "sucursales": sucursales,
        "cursos": cursos,

        "sucursal_id": sucursal_id,
        "curso_id": curso_id,
        "q": q,
    }
    return render(request, "paralelos/paralelos_lista.html", context)


def paralelos_crear(request):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    # GET para filtrar cursos por sucursal
    sucursal_id = request.GET.get("sucursal", "").strip()

    sucursales = Sucursal.objects.filter(activa=True).order_by("nombre")

    # Default: Latacunga (Matriz)
    if not sucursal_id:
        s_lat = Sucursal.objects.filter(nombre="Latacunga (Matriz)").first()
        if s_lat:
            sucursal_id = str(s_lat.id)

    cursos = Curso.objects.select_related("sucursal").all().order_by("sucursal__nombre", "nombre")
    if sucursal_id:
        cursos = cursos.filter(sucursal_id=sucursal_id)

    if request.method == "POST":
        nombre = (request.POST.get("nombre") or "").strip()
        curso_id = (request.POST.get("curso") or "").strip()
        sucursal_context = (request.POST.get("sucursal_context") or "").strip()

        if not nombre or not curso_id:
            messages.error(request, "Nombre y curso son obligatorios.")
            return redirect(f"{request.path}?sucursal={sucursal_context}")

        curso = get_object_or_404(Curso.objects.select_related("sucursal"), id=curso_id)

        # Validación duplicado
        if Paralelo.objects.filter(curso=curso, nombre=nombre).exists():
            messages.error(request, "Ese paralelo ya existe para el curso seleccionado.")
            return redirect(f"{request.path}?sucursal={curso.sucursal_id}")

        Paralelo.objects.create(nombre=nombre, curso=curso)
        messages.success(request, "Paralelo creado correctamente.")
        return redirect("paralelos_lista")

    context = {
        "sucursales": sucursales,
        "sucursal_id": sucursal_id,
        "cursos": cursos,
    }
    return render(request, "paralelos/paralelos_crear.html", context)


def paralelos_editar(request, paralelo_id):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    paralelo = get_object_or_404(Paralelo.objects.select_related("curso__sucursal"), id=paralelo_id)

    sucursal_id = request.GET.get("sucursal", "").strip() or str(paralelo.curso.sucursal_id)

    sucursales = Sucursal.objects.filter(activa=True).order_by("nombre")
    cursos = Curso.objects.select_related("sucursal").all().order_by("sucursal__nombre", "nombre")
    if sucursal_id:
        cursos = cursos.filter(sucursal_id=sucursal_id)

    if request.method == "POST":
        nombre = (request.POST.get("nombre") or "").strip()
        curso_id = (request.POST.get("curso") or "").strip()

        if not nombre or not curso_id:
            messages.error(request, "Nombre y curso son obligatorios.")
            return redirect("paralelos_editar", paralelo_id=paralelo.id)

        curso = get_object_or_404(Curso.objects.select_related("sucursal"), id=curso_id)

        # Validar duplicado excepto el actual
        if Paralelo.objects.exclude(id=paralelo.id).filter(curso=curso, nombre=nombre).exists():
            messages.error(request, "Ese paralelo ya existe en ese curso.")
            return redirect("paralelos_editar", paralelo_id=paralelo.id)

        paralelo.nombre = nombre
        paralelo.curso = curso
        paralelo.save()

        messages.success(request, "Paralelo actualizado correctamente.")
        return redirect("paralelos_lista")

    return render(request, "paralelos/paralelos_editar.html", {
        "paralelo": paralelo,
        "sucursales": sucursales,
        "sucursal_id": sucursal_id,
        "cursos": cursos,
    })
# ========================================================================= AÑO LECTIVO =====================

def anios_lista(request):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    anios = AnioLectivo.objects.all().order_by("-activo", "-id", "-nombre")

    return render(request, "anios/anios_lista.html", {
        "anios": anios,
    })


def anios_crear(request):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    if request.method == "POST":
        nombre = (request.POST.get("nombre") or "").strip()
        fecha_inicio = request.POST.get("fecha_inicio") or None
        fecha_fin = request.POST.get("fecha_fin") or None
        activo = (request.POST.get("activo") == "on")

        # Validaciones básicas
        if not nombre or not fecha_inicio or not fecha_fin:
            messages.error(request, "Nombre, fecha inicio y fecha fin son obligatorios.")
            return redirect("anios_crear")

        # validar formato/orden de fechas
        try:
            fi = datetime.strptime(fecha_inicio, "%Y-%m-%d").date()
            ff = datetime.strptime(fecha_fin, "%Y-%m-%d").date()
            if ff < fi:
                messages.error(request, "La fecha fin no puede ser menor que la fecha inicio.")
                return redirect("anios_crear")
        except ValueError:
            messages.error(request, "Formato de fechas inválido.")
            return redirect("anios_crear")

        # Validar año repetido (nombre)
        if AnioLectivo.objects.filter(nombre__iexact=nombre).exists():
            messages.error(request, "Ese año lectivo ya existe.")
            return redirect("anios_crear")

        # Guardado seguro: si activo=True, desactiva los demás en una transacción
        with transaction.atomic():
            if activo:
                AnioLectivo.objects.update(activo=False)

            AnioLectivo.objects.create(
                nombre=nombre,
                fecha_inicio=fi,
                fecha_fin=ff,
                activo=activo
            )

        messages.success(request, "Año lectivo creado correctamente.")
        return redirect("anios_lista")

    return render(request, "anios/anios_crear.html")


def anios_editar(request, anio_id):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    anio = get_object_or_404(AnioLectivo, id=anio_id)

    if request.method == "POST":
        nombre = (request.POST.get("nombre") or "").strip()
        fecha_inicio = request.POST.get("fecha_inicio") or None
        fecha_fin = request.POST.get("fecha_fin") or None
        activo = (request.POST.get("activo") == "on")

        if not nombre or not fecha_inicio or not fecha_fin:
            messages.error(request, "Nombre, fecha inicio y fecha fin son obligatorios.")
            return redirect("anios_editar", anio_id=anio.id)

        try:
            fi = datetime.strptime(fecha_inicio, "%Y-%m-%d").date()
            ff = datetime.strptime(fecha_fin, "%Y-%m-%d").date()
            if ff < fi:
                messages.error(request, "La fecha fin no puede ser menor que la fecha inicio.")
                return redirect("anios_editar", anio_id=anio.id)
        except ValueError:
            messages.error(request, "Formato de fechas inválido.")
            return redirect("anios_editar", anio_id=anio.id)

        if AnioLectivo.objects.exclude(id=anio.id).filter(nombre__iexact=nombre).exists():
            messages.error(request, "Ya existe un año lectivo con ese nombre.")
            return redirect("anios_editar", anio_id=anio.id)

        with transaction.atomic():
            if activo:
                AnioLectivo.objects.exclude(id=anio.id).update(activo=False)

            anio.nombre = nombre
            anio.fecha_inicio = fi
            anio.fecha_fin = ff
            anio.activo = activo
            anio.save()

        messages.success(request, "Año lectivo actualizado correctamente.")
        return redirect("anios_lista")

    return render(request, "anios/anios_editar.html", {
        "anio": anio
    })


def anios_activar(request, anio_id):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    with transaction.atomic():
        AnioLectivo.objects.update(activo=False)
        anio = get_object_or_404(AnioLectivo, id=anio_id)
        anio.activo = True
        anio.save()

    messages.success(request, f"Año lectivo {anio.nombre} activado.")
    return redirect("anios_lista")
# ========================================================================= ASIGNATURAS =====================


def asignaturas_lista(request):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    sucursal_id = request.GET.get("sucursal", "").strip()
    curso_id = request.GET.get("curso", "").strip()
    q = request.GET.get("q", "").strip()

    # ✅ Default: Latacunga (Matriz)
    if not sucursal_id:
        s_lat = Sucursal.objects.filter(nombre="Latacunga (Matriz)").first()
        if s_lat:
            sucursal_id = str(s_lat.id)

    asignaturas = Asignatura.objects.select_related("curso__sucursal").all()

    if sucursal_id:
        asignaturas = asignaturas.filter(curso__sucursal_id=sucursal_id)

    if curso_id:
        asignaturas = asignaturas.filter(curso_id=curso_id)

    if q:
        asignaturas = asignaturas.filter(
            Q(nombre__icontains=q) |
            Q(curso__nombre__icontains=q) |
            Q(curso__sucursal__nombre__icontains=q)
        )

    asignaturas = asignaturas.order_by(
        "curso__sucursal__nombre",
        "curso__nombre",
        "nombre"
    )

    # combos
    sucursales = Sucursal.objects.filter(activa=True).order_by("nombre")
    cursos = Curso.objects.select_related("sucursal").all().order_by("sucursal__nombre", "nombre")

    # si hay sucursal elegida, cursos solo de esa sucursal
    if sucursal_id:
        cursos = cursos.filter(sucursal_id=sucursal_id)

    context = {
        "asignaturas": asignaturas,
        "sucursales": sucursales,
        "cursos": cursos,
        "sucursal_id": sucursal_id,
        "curso_id": curso_id,
        "q": q,
    }
    return render(request, "asignaturas/asignaturas_lista.html", context)


def asignaturas_crear(request):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    # GET para filtrar cursos por sucursal
    sucursal_id = request.GET.get("sucursal", "").strip()

    sucursales = Sucursal.objects.filter(activa=True).order_by("nombre")

    # ✅ Default: Latacunga (Matriz)
    if not sucursal_id:
        s_lat = Sucursal.objects.filter(nombre="Latacunga (Matriz)").first()
        if s_lat:
            sucursal_id = str(s_lat.id)

    cursos = Curso.objects.select_related("sucursal").all().order_by("sucursal__nombre", "nombre")
    if sucursal_id:
        cursos = cursos.filter(sucursal_id=sucursal_id)

    if request.method == "POST":
        nombre = (request.POST.get("nombre") or "").strip()
        curso_id = (request.POST.get("curso") or "").strip()
        sucursal_context = (request.POST.get("sucursal_context") or "").strip()

        if not nombre or not curso_id:
            messages.error(request, "Nombre y curso son obligatorios.")
            return redirect(f"{request.path}?sucursal={sucursal_context}")

        curso = get_object_or_404(Curso.objects.select_related("sucursal"), id=curso_id)

        # ✅ Validación duplicado
        if Asignatura.objects.filter(nombre=nombre, curso=curso).exists():
            messages.error(request, "Ya existe esta asignatura para este curso.")
            return redirect(f"{request.path}?sucursal={curso.sucursal_id}")

        Asignatura.objects.create(nombre=nombre, curso=curso)
        messages.success(request, "Asignatura creada correctamente.")
        return redirect("asignaturas_lista")

    context = {
        "sucursales": sucursales,
        "sucursal_id": sucursal_id,
        "cursos": cursos,
    }
    return render(request, "asignaturas/asignaturas_crear.html", context)


def asignaturas_editar(request, asignatura_id):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    asignatura = get_object_or_404(Asignatura.objects.select_related("curso__sucursal"), id=asignatura_id)

    sucursal_id = request.GET.get("sucursal", "").strip() or str(asignatura.curso.sucursal_id)

    sucursales = Sucursal.objects.filter(activa=True).order_by("nombre")
    cursos = Curso.objects.select_related("sucursal").all().order_by("sucursal__nombre", "nombre")

    if sucursal_id:
        cursos = cursos.filter(sucursal_id=sucursal_id)

    if request.method == "POST":
        nombre = (request.POST.get("nombre") or "").strip()
        curso_id = (request.POST.get("curso") or "").strip()

        if not nombre or not curso_id:
            messages.error(request, "Nombre y curso son obligatorios.")
            return redirect("asignaturas_editar", asignatura_id=asignatura.id)

        curso = get_object_or_404(Curso.objects.select_related("sucursal"), id=curso_id)

        # ✅ duplicado excepto el actual
        if Asignatura.objects.exclude(id=asignatura.id).filter(nombre=nombre, curso=curso).exists():
            messages.error(request, "Esta asignatura ya existe para este curso.")
            return redirect("asignaturas_editar", asignatura_id=asignatura.id)

        asignatura.nombre = nombre
        asignatura.curso = curso
        asignatura.save()

        messages.success(request, "Asignatura actualizada correctamente.")
        return redirect("asignaturas_lista")

    return render(request, "asignaturas/asignaturas_editar.html", {
        "asignatura": asignatura,
        "sucursales": sucursales,
        "sucursal_id": sucursal_id,
        "cursos": cursos,
    })

# ========================================================================= DOCENTE ASIGANACION =====================

def docente_asignacion_lista(request):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    sucursal_id = request.GET.get("sucursal", "")
    anio_id = request.GET.get("anio", "")
    paralelo_id = request.GET.get("paralelo", "")
    q = request.GET.get("q", "").strip()

    # Default: Latacunga (Matriz)
    if not sucursal_id:
        s_lat = Sucursal.objects.filter(nombre="Latacunga (Matriz)").first()
        if s_lat:
            sucursal_id = str(s_lat.id)

    # Default: Año lectivo activo 
    if not anio_id:
        anio_activo = AnioLectivo.objects.filter(activo=True).first()
        if anio_activo:
            anio_id = str(anio_activo.id)

    asignaciones = DocenteAsignacion.objects.select_related(
        "docente__usuario",
        "asignatura__curso__sucursal",
        "paralelo__curso__sucursal",
        "anio_lectivo"
    )

    # filtros
    if sucursal_id:
        asignaciones = asignaciones.filter(paralelo__curso__sucursal_id=sucursal_id)

    if anio_id:
        asignaciones = asignaciones.filter(anio_lectivo_id=anio_id)

    if paralelo_id:
        asignaciones = asignaciones.filter(paralelo_id=paralelo_id)

    if q:
        asignaciones = asignaciones.filter(
            Q(docente__usuario__nombres__icontains=q) |
            Q(docente__usuario__apellido_paterno__icontains=q) |
            Q(docente__usuario__cedula__icontains=q) |
            Q(asignatura__nombre__icontains=q) |
            Q(paralelo__curso__nombre__icontains=q) |
            Q(paralelo__nombre__icontains=q)
        )

    asignaciones = asignaciones.order_by(
        "paralelo__curso__sucursal__nombre",
        "anio_lectivo__nombre",
        "paralelo__curso__nombre",
        "paralelo__nombre",
        "asignatura__nombre"
    )

    # combos
    sucursales = Sucursal.objects.filter(activa=True).order_by("nombre")
    anios = AnioLectivo.objects.order_by("-activo", "-id")

    paralelos = Paralelo.objects.select_related("curso__sucursal").order_by(
        "curso__sucursal__nombre", "curso__nombre", "nombre"
    )

    # mostrar en combo solo paralelos de la sucursal elegida
    if sucursal_id:
        paralelos = paralelos.filter(curso__sucursal_id=sucursal_id)

    context = {
        "asignaciones": asignaciones,
        "sucursales": sucursales,
        "anios": anios,
        "paralelos": paralelos,
        "sucursal_id": sucursal_id,
        "anio_id": anio_id,
        "paralelo_id": paralelo_id,
        "q": q,
    }

    return render(request, "docentes/asignacion_lista.html", context)

def docente_asignacion_crear(request):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    # GET para filtrar
    sucursal_id = request.GET.get("sucursal", "")
    paralelo_id = request.GET.get("paralelo", "")
    anio_id = request.GET.get("anio", "")

    # Default: Latacunga (Matriz)
    if not sucursal_id:
        s_lat = Sucursal.objects.filter(nombre="Latacunga (Matriz)").first()
        if s_lat:
            sucursal_id = str(s_lat.id)

    sucursales = Sucursal.objects.filter(activa=True).order_by("nombre")
    docentes = Docente.objects.select_related("usuario").order_by("usuario__apellido_paterno", "usuario__nombres")
    anios = AnioLectivo.objects.filter(activo=True).order_by("-id")

    if not anio_id:
        anio_activo = AnioLectivo.objects.filter(activo=True).first()
        if anio_activo:
            anio_id = str(anio_activo.id)

    paralelos = Paralelo.objects.select_related("curso__sucursal").all()
    if sucursal_id:
        paralelos = paralelos.filter(curso__sucursal_id=sucursal_id)
    paralelos = paralelos.order_by("curso__nombre", "nombre")

    # asignaturas dependen del paralelo seleccionado
    asignaturas = Asignatura.objects.select_related("curso").none()
    paralelo_sel = None
    if paralelo_id:
        paralelo_sel = get_object_or_404(Paralelo, id=paralelo_id)
        asignaturas = Asignatura.objects.select_related("curso").filter(
            curso_id=paralelo_sel.curso_id
        ).order_by("nombre")

    if request.method == "POST":
        docente_id = request.POST.get("docente")
        asignatura_id = request.POST.get("asignatura")
        paralelo_id_post = request.POST.get("paralelo")
        anio_id_post = request.POST.get("anio_lectivo")

        docente = get_object_or_404(Docente, id=docente_id)
        asignatura = get_object_or_404(Asignatura, id=asignatura_id)
        paralelo = get_object_or_404(Paralelo, id=paralelo_id_post)
        anio = get_object_or_404(AnioLectivo, id=anio_id_post)

        # URL base para volver al formulario con filtros
        url = reverse("docente_asignacion_crear")
        back = f"{url}?sucursal={paralelo.curso.sucursal_id}&paralelo={paralelo.id}&anio={anio.id}"

        # Validación: asignatura pertenece al curso del paralelo
        if asignatura.curso_id != paralelo.curso_id:
            messages.error(request, "Error: la asignatura seleccionada no pertenece al curso/paralelo elegido.")
            return HttpResponseRedirect(back)

        # Evita duplicados
        if DocenteAsignacion.objects.filter(
            docente=docente,
            asignatura=asignatura,
            paralelo=paralelo,
            anio_lectivo=anio
        ).exists():
            messages.error(request, "Esa asignación ya existe.")
            return HttpResponseRedirect(back)

        DocenteAsignacion.objects.create(
            docente=docente,
            asignatura=asignatura,
            paralelo=paralelo,
            anio_lectivo=anio
        )
        messages.success(request, "Asignación creada correctamente.")
        return redirect("docente_asignacion_lista")

    context = {
        "sucursales": sucursales,
        "docentes": docentes,
        "paralelos": paralelos,
        "asignaturas": asignaturas,
        "anios": anios,
        "sucursal_id": sucursal_id,
        "paralelo_id": paralelo_id,
        "paralelo_sel": paralelo_sel,
        "anio_id": anio_id,  # opcional para dejar seleccionado
    }
    return render(request, "docentes/asignacion_crear.html", context)

# ========================================================================= DOCENTE =====================

def docente_cursos(request):
    if request.session.get("usuario_rol") != "docente":
        return redirect("login")

    usuario_id = request.session.get("usuario_id")

    # obtener el objeto Docente
    docente = get_object_or_404(Docente, usuario_id=usuario_id)

    # asignaciones del docente
    asignaciones = DocenteAsignacion.objects.filter(docente=docente).select_related(
        "asignatura", "paralelo", "anio_lectivo"
    )

    context = {
        "asignaciones": asignaciones
    }
    return render(request, "docentes/docente_cursos.html", context)



def mis_cursos(request):
    if request.session.get("usuario_rol") != "docente":
        return redirect("login")

    docente = get_object_or_404(Docente, usuario_id=request.session.get("usuario_id"))

    # Lista de años lectivos (para el filtro)
    anios = AnioLectivo.objects.all().order_by("-nombre")

    # Año seleccionado por GET
    anio_id = request.GET.get("anio", "").strip()

    # Si no viene anio por GET -> usar el año activo
    anio_activo = AnioLectivo.objects.filter(activo=True).first()

    if not anio_id:
        # por defecto: año activo
        if anio_activo:
            anio_id = str(anio_activo.id)

    # Query base
    asignaciones_qs = DocenteAsignacion.objects.filter(docente=docente).select_related(
        "asignatura",
        "paralelo__curso__sucursal",
        "anio_lectivo"
    )

    # Filtrar por año si existe
    if anio_id:
        asignaciones_qs = asignaciones_qs.filter(anio_lectivo_id=anio_id)

    # Orden bonito
    asignaciones_qs = asignaciones_qs.order_by(
        "anio_lectivo__nombre",
        "paralelo__curso__nombre",
        "paralelo__nombre",
        "asignatura__nombre"
    )

    # Aviso si no hay año activo y no seleccionó ninguno
    if not AnioLectivo.objects.filter(activo=True).exists() and not request.GET.get("anio"):
        messages.warning(request, "No existe un año lectivo activo. Selecciona uno para ver tus cursos.")

    context = {
        "asignaciones": asignaciones_qs,
        "anios": anios,
        "anio_id": anio_id,
        "anio_activo": anio_activo,
    }
    return render(request, "docentes/mis_cursos.html", context)
    
def mis_cursos_notas(request, asignacion_id):
    if request.session.get("usuario_rol") != "docente":
        return redirect("login")
    docente = get_object_or_404(Docente, usuario_id=request.session.get("usuario_id"))
    asignacion = get_object_or_404(DocenteAsignacion, id=asignacion_id, docente=docente)

    # alumnos de este curso
    matriculas = Matricula.objects.filter(
        paralelo=asignacion.paralelo,
        anio_lectivo=asignacion.anio_lectivo
    ).select_related("estudiante")

    # buscar notas
    filas = []
    for m in matriculas:
        n = Nota.objects.filter(matricula=m, asignacion=asignacion).first()

        filas.append({
            "matricula": m,
            "nota": n
        })

    return render(request, "docentes/mis_cursos_notas.html", {
        "asignacion": asignacion,
        "filas": filas
    })

# ========================================================================= ESTUDIANTES =====================

def estudiantes_lista(request):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    q = (request.GET.get("q") or "").strip()
    sucursal_id = (request.GET.get("sucursal") or "").strip()

    # Default: Latacunga (Matriz)
    if not sucursal_id:
        s_lat = Sucursal.objects.filter(nombre="Latacunga (Matriz)").first()
        if s_lat:
            sucursal_id = str(s_lat.id)

    estudiantes = Estudiante.objects.select_related("sucursal").all()

    if sucursal_id:
        estudiantes = estudiantes.filter(sucursal_id=sucursal_id)

    if q:
        estudiantes = estudiantes.filter(
            Q(cedula__icontains=q) |
            Q(nombres__icontains=q) |
            Q(apellido_paterno__icontains=q) |
            Q(apellido_materno__icontains=q)
        )

    estudiantes = estudiantes.order_by("sucursal__nombre", "apellido_paterno", "apellido_materno", "nombres")
    sucursales = Sucursal.objects.filter(activa=True).order_by("nombre")

    return render(request, "estudiantes/estudiantes_lista.html", {
        "estudiantes": estudiantes,
        "q": q,
        "sucursales": sucursales,
        "sucursal_id": sucursal_id,
    })


def estudiantes_crear(request):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    sucursal_id = (request.GET.get("sucursal") or "").strip()
    sucursales = Sucursal.objects.filter(activa=True).order_by("nombre")

    # Default: Latacunga (Matriz)
    if not sucursal_id:
        s_lat = Sucursal.objects.filter(nombre="Latacunga (Matriz)").first()
        if s_lat:
            sucursal_id = str(s_lat.id)

    if request.method == "POST":
        cedula = (request.POST.get("cedula") or "").strip()
        nombres = (request.POST.get("nombres") or "").strip()
        apellido_paterno = (request.POST.get("apellido_paterno") or "").strip()
        apellido_materno = (request.POST.get("apellido_materno") or "").strip()
        fecha_nacimiento = request.POST.get("fecha_nacimiento") or None
        telefono = (request.POST.get("telefono") or "").strip() or None
        direccion = (request.POST.get("direccion") or "").strip() or None
        sucursal_id_post = (request.POST.get("sucursal") or "").strip()
        sucursal_context = (request.POST.get("sucursal_context") or "").strip()

        if not cedula or not nombres or not apellido_paterno or not apellido_materno or not sucursal_id_post:
            messages.error(request, "Cédula, nombres, apellidos y sucursal son obligatorios.")
            return redirect(f"{request.path}?sucursal={sucursal_context}")

        if Estudiante.objects.filter(cedula=cedula).exists():
            messages.error(request, "La cédula ya está registrada.")
            return redirect(f"{request.path}?sucursal={sucursal_context}")

        sucursal = get_object_or_404(Sucursal, id=sucursal_id_post)

        try:
            Estudiante.objects.create(
                cedula=cedula,
                nombres=nombres,
                apellido_paterno=apellido_paterno,
                apellido_materno=apellido_materno,
                fecha_nacimiento=fecha_nacimiento,
                telefono=telefono,
                direccion=direccion,
                sucursal=sucursal
            )
        except ValidationError as e:
            if hasattr(e, "message_dict"):
                msg = (
                    e.message_dict.get("cedula")
                    or e.message_dict.get("fecha_nacimiento")
                    or e.messages
                )
            else:
                msg = e.messages

            if isinstance(msg, list):
                msg = " ".join(msg)

            messages.error(request, msg)
            return redirect(f"{request.path}?sucursal={sucursal_context}")

        messages.success(request, "Estudiante creado correctamente.")
        return redirect("estudiantes_lista")

    return render(request, "estudiantes/estudiantes_crear.html", {
        "sucursales": sucursales,
        "sucursal_id": sucursal_id,
    })


def estudiantes_editar(request, estudiante_id):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    estudiante = get_object_or_404(Estudiante.objects.select_related("sucursal"), id=estudiante_id)
    sucursales = Sucursal.objects.filter(activa=True).order_by("nombre")

    if request.method == "POST":
        
        nombres = (request.POST.get("nombres") or "").strip()
        apellido_paterno = (request.POST.get("apellido_paterno") or "").strip()
        apellido_materno = (request.POST.get("apellido_materno") or "").strip()
        fecha_nacimiento = request.POST.get("fecha_nacimiento") or None
        telefono = (request.POST.get("telefono") or "").strip() or None
        direccion = (request.POST.get("direccion") or "").strip() or None
        sucursal_id = (request.POST.get("sucursal") or "").strip()

        if not nombres or not apellido_paterno or not apellido_materno or not sucursal_id:
            messages.error(request, "Nombres, apellidos y sucursal son obligatorios.")
            return redirect("estudiantes_editar", estudiante_id=estudiante.id)
        
        estudiante.nombres = nombres
        estudiante.apellido_paterno = apellido_paterno
        estudiante.apellido_materno = apellido_materno
        estudiante.fecha_nacimiento = fecha_nacimiento
        estudiante.telefono = telefono
        estudiante.direccion = direccion
        estudiante.sucursal = get_object_or_404(Sucursal, id=sucursal_id)
        try:
            estudiante.save()
        except ValidationError as e:
            if hasattr(e, "message_dict"):
                msg = (
                    e.message_dict.get("cedula")
                    or e.message_dict.get("fecha_nacimiento")
                    or e.messages
                )
            else:
                msg = e.messages

            if isinstance(msg, list):
                msg = " ".join(msg)

            messages.error(request, msg)
            return redirect("estudiantes_editar", estudiante_id=estudiante.id)

        messages.success(request, "Estudiante actualizado correctamente.")
        return redirect("estudiantes_lista")

    return render(request, "estudiantes/estudiantes_editar.html", {
        "estudiante": estudiante,
        "sucursales": sucursales,
    })

# ========================================================================= MATRICUAS =====================

def matriculas_lista(request):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    q = request.GET.get("q", "").strip()
    sucursal_id = request.GET.get("sucursal", "").strip()
    anio_id = request.GET.get("anio_lectivo", "").strip()
    paralelo_id = request.GET.get("paralelo", "").strip()

    # combos
    sucursales = Sucursal.objects.filter(activa=True).order_by("nombre")
    anios = AnioLectivo.objects.all().order_by("-activo", "-id")  # activo primero

    # ✅ Default: Latacunga (Matriz)
    if not sucursal_id:
        s_lat = Sucursal.objects.filter(nombre="Latacunga (Matriz)").first()
        if s_lat:
            sucursal_id = str(s_lat.id)

    # ✅ Default: Año activo
    anio_activo = AnioLectivo.objects.filter(activo=True).first()
    if not anio_id and anio_activo:
        anio_id = str(anio_activo.id)

    matriculas = Matricula.objects.select_related(
        "estudiante", "paralelo__curso__sucursal", "anio_lectivo"
    ).all()

    # filtros
    if anio_id:
        matriculas = matriculas.filter(anio_lectivo_id=anio_id)

    if sucursal_id:
        matriculas = matriculas.filter(paralelo__curso__sucursal_id=sucursal_id)

    if paralelo_id:
        matriculas = matriculas.filter(paralelo_id=paralelo_id)

    if q:
        matriculas = matriculas.filter(
            Q(estudiante__cedula__icontains=q) |
            Q(estudiante__nombres__icontains=q) |
            Q(estudiante__apellido_paterno__icontains=q) |
            Q(estudiante__apellido_materno__icontains=q) |
            Q(paralelo__curso__nombre__icontains=q) |
            Q(paralelo__nombre__icontains=q)
        )

    matriculas = matriculas.order_by(
        "-anio_lectivo__activo",
        "-anio_lectivo__id",
        "paralelo__curso__nombre",
        "paralelo__nombre",
        "estudiante__apellido_paterno",
        "estudiante__nombres",
    )

    # paralelos para filtro (solo de la sucursal elegida)
    paralelos = Paralelo.objects.select_related("curso__sucursal").order_by(
        "curso__nombre", "nombre"
    )
    if sucursal_id:
        paralelos = paralelos.filter(curso__sucursal_id=sucursal_id)

    context = {
        "matriculas": matriculas,
        "q": q,
        "sucursales": sucursales,
        "anios": anios,
        "paralelos": paralelos,
        "sucursal_id": sucursal_id,
        "anio_id": anio_id,
        "paralelo_id": paralelo_id,
        "anio_activo": anio_activo,
    }
    return render(request, "matriculas/matriculas_lista.html", context)

def _flash_validation_error(request, e: ValidationError):
    if hasattr(e, "message_dict"):
        for _, msgs in e.message_dict.items():
            if isinstance(msgs, (list, tuple)):
                for msg in msgs:
                    messages.error(request, str(msg))
            else:
                messages.error(request, str(msgs))
    else:
        # e.messages suele venir como lista
        if hasattr(e, "messages"):
            for msg in e.messages:
                messages.error(request, str(msg))
        else:
            messages.error(request, str(e))


def matriculas_crear(request):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    sucursal_id = (request.GET.get("sucursal") or "").strip()

    if not sucursal_id:
        s_lat = Sucursal.objects.filter(nombre="Latacunga (Matriz)").first()
        if s_lat:
            sucursal_id = str(s_lat.id)

    sucursales = Sucursal.objects.filter(activa=True).order_by("nombre")

    # Para históricos: dejamos escoger cualquier año (incluye activo)
    anios = AnioLectivo.objects.all().order_by("-activo", "-id")
    anio_activo = AnioLectivo.objects.filter(activo=True).first()

    estudiantes = Estudiante.objects.none()
    paralelos = Paralelo.objects.none()

    if sucursal_id:
        estudiantes = Estudiante.objects.filter(sucursal_id=sucursal_id).order_by(
            "apellido_paterno", "apellido_materno", "nombres"
        )
        paralelos = Paralelo.objects.select_related("curso__sucursal").filter(
            curso__sucursal_id=sucursal_id
        ).order_by("curso__nombre", "nombre")

    if request.method == "POST":
        estudiante_id = (request.POST.get("estudiante") or "").strip()
        paralelo_id = (request.POST.get("paralelo") or "").strip()
        anio_id = (request.POST.get("anio_lectivo") or "").strip()
        tipo_programa = (request.POST.get("tipo_programa") or "").strip()

        jornada = request.POST.get("jornada") or None
        temporalidad = request.POST.get("temporalidad") or None
        estado_estudiante = request.POST.get("estado_estudiante") or None
        observaciones = request.POST.get("observaciones") or None

        sucursal_id_post = request.POST.get("sucursal_context") or sucursal_id or ""

        if not (estudiante_id and paralelo_id and anio_id and tipo_programa):
            messages.error(request, "Complete los campos obligatorios.")
            return redirect(f"{request.path}?sucursal={sucursal_id_post}")

        estudiante = get_object_or_404(Estudiante, id=estudiante_id)
        paralelo = get_object_or_404(Paralelo.objects.select_related("curso__sucursal"), id=paralelo_id)
        anio = get_object_or_404(AnioLectivo, id=anio_id)

        try:
            matricula = Matricula(
                estudiante=estudiante,
                paralelo=paralelo,
                anio_lectivo=anio,
                tipo_programa=tipo_programa,
                jornada=jornada,
                temporalidad=temporalidad,
                estado_estudiante=estado_estudiante,
                observaciones=observaciones,
            )
            matricula.save()

        except ValidationError as e:
            _flash_validation_error(request, e)
            return redirect(f"{request.path}?sucursal={sucursal_id_post}")

        except IntegrityError:
            messages.error(request, "Ya existe una matrícula para este estudiante en el año lectivo seleccionado.")
            return redirect(f"{request.path}?sucursal={sucursal_id_post}")

        messages.success(request, "Matrícula registrada correctamente.")
        return redirect("matriculas_lista")

    context = {
        "sucursales": sucursales,
        "sucursal_id": sucursal_id,
        "estudiantes": estudiantes,
        "paralelos": paralelos,
        "anio_activo": anio_activo,
        "anios": anios,  # úsalo en el select para escoger año
    }
    return render(request, "matriculas/matriculas_crear.html", context)


def matriculas_editar(request, matricula_id):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    matricula = get_object_or_404(
        Matricula.objects.select_related("estudiante__sucursal", "paralelo__curso__sucursal", "anio_lectivo"),
        id=matricula_id
    )

    sucursal_id = matricula.paralelo.curso.sucursal_id

    estudiantes = Estudiante.objects.filter(sucursal_id=sucursal_id).order_by(
        "apellido_paterno", "apellido_materno", "nombres"
    )
    paralelos = Paralelo.objects.select_related("curso__sucursal").filter(
        curso__sucursal_id=sucursal_id
    ).order_by("curso__nombre", "nombre")

    # Para históricos: permitimos editar año lectivo a cualquiera
    anios = AnioLectivo.objects.all().order_by("-activo", "-id")

    if request.method == "POST":
        estudiante_id = (request.POST.get("estudiante") or "").strip()
        paralelo_id = (request.POST.get("paralelo") or "").strip()
        anio_id = (request.POST.get("anio_lectivo") or "").strip()
        tipo_programa = (request.POST.get("tipo_programa") or "").strip()

        jornada = request.POST.get("jornada") or None
        temporalidad = request.POST.get("temporalidad") or None
        estado_estudiante = request.POST.get("estado_estudiante") or None
        observaciones = request.POST.get("observaciones") or None

        if not (estudiante_id and paralelo_id and anio_id and tipo_programa):
            messages.error(request, "Complete los campos obligatorios.")
            return redirect("matriculas_editar", matricula_id=matricula.id)

        estudiante = get_object_or_404(Estudiante, id=estudiante_id)
        paralelo = get_object_or_404(Paralelo.objects.select_related("curso__sucursal"), id=paralelo_id)
        anio = get_object_or_404(AnioLectivo, id=anio_id)

        matricula.estudiante = estudiante
        matricula.paralelo = paralelo
        matricula.anio_lectivo = anio
        matricula.tipo_programa = tipo_programa
        matricula.jornada = jornada
        matricula.temporalidad = temporalidad
        matricula.estado_estudiante = estado_estudiante
        matricula.observaciones = observaciones

        try:
            matricula.save()

        except ValidationError as e:
            _flash_validation_error(request, e)
            return redirect("matriculas_editar", matricula_id=matricula.id)

        except IntegrityError:
            messages.error(request, "No se pudo guardar: ya existe una matrícula para ese estudiante en ese año lectivo.")
            return redirect("matriculas_editar", matricula_id=matricula.id)

        messages.success(request, "Matrícula actualizada correctamente.")
        return redirect("matriculas_lista")

    context = {
        "matricula": matricula,
        "estudiantes": estudiantes,
        "paralelos": paralelos,
        "anios": anios,
    }
    return render(request, "matriculas/matriculas_editar.html", context)


# ========================== PROMO ======================================

def _round2(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _to_decimal_0_10(value: str):
    s = (value or "").strip().replace(",", ".")
    if s == "":
        raise ValueError("vacío")
    d = Decimal(s)
    if d < Decimal("0") or d > Decimal("10"):
        raise ValueError("rango")
    return _round2(d)

def promociones_lista(request):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    q = (request.GET.get("q") or "").strip()
    anio_id = (request.GET.get("anio") or "").strip()
    sucursal_id = (request.GET.get("sucursal") or "").strip()

    sucursales = Sucursal.objects.filter(activa=True).order_by("nombre")

    # Default: Latacunga (Matriz) (igual que matrículas)
    if not sucursal_id:
        s_lat = Sucursal.objects.filter(nombre="Latacunga (Matriz)").first()
        if s_lat:
            sucursal_id = str(s_lat.id)

    promos = Promocion.objects.select_related(
        "estudiante", "anio_lectivo", "curso__sucursal"
    ).all()

    if sucursal_id:
        promos = promos.filter(curso__sucursal_id=sucursal_id)

    if anio_id:
        promos = promos.filter(anio_lectivo_id=anio_id)

    if q:
        promos = promos.filter(
            Q(estudiante__cedula__icontains=q)
            | Q(estudiante__nombres__icontains=q)
            | Q(estudiante__apellido_paterno__icontains=q)
            | Q(estudiante__apellido_materno__icontains=q)
            | Q(anio_lectivo__nombre__icontains=q)
            | Q(curso__nombre__icontains=q)
        )

    promos = promos.order_by(
        "-anio_lectivo__id",
        "estudiante__apellido_paterno",
        "curso__orden",
        "curso__nombre",
    )

    anios = AnioLectivo.objects.all().order_by("-id")

    return render(request, "promociones/promociones_lista.html", {
        "promos": promos,
        "q": q,
        "anios": anios,
        "anio_id": anio_id,
        "sucursales": sucursales,
        "sucursal_id": sucursal_id,
    })

def promociones_crear(request):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    # ✅ Sucursal por GET (para filtrar estudiantes/cursos)
    sucursal_id = (request.GET.get("sucursal") or "").strip()

    # ✅ Default: Latacunga (Matriz)
    if not sucursal_id:
        s_lat = Sucursal.objects.filter(nombre="Latacunga (Matriz)").first()
        if s_lat:
            sucursal_id = str(s_lat.id)

    sucursales = Sucursal.objects.filter(activa=True).order_by("nombre")

    # combos
    estudiantes = Estudiante.objects.all().order_by("apellido_paterno", "apellido_materno", "nombres")
    cursos = Curso.objects.all().order_by("orden", "nombre")
    anios = AnioLectivo.objects.all().order_by("-id")

    # ✅ filtrar por sucursal
    if sucursal_id:
        estudiantes = estudiantes.filter(sucursal_id=sucursal_id)
        cursos = cursos.filter(sucursal_id=sucursal_id)

    if request.method == "POST":
        # ✅ mantener sucursal al validar/redirect
        sucursal_id_post = (request.POST.get("sucursal_context") or sucursal_id or "").strip()

        estudiante_id = (request.POST.get("estudiante") or "").strip()
        anio_id = (request.POST.get("anio_lectivo") or "").strip()
        curso_id = (request.POST.get("curso") or "").strip()

        # En histórico: SOLO AUTO o RETIRADO
        resultado_input = (request.POST.get("resultado") or "").strip()

        comportamiento = (request.POST.get("comportamiento") or "").strip() or None
        observacion = (request.POST.get("observacion") or "").strip() or None

        asignaturas = request.POST.getlist("asignatura_nombre[]")
        califs = request.POST.getlist("calificacion[]")

        # 1) Validación mínima
        if not (estudiante_id and anio_id and curso_id and resultado_input):
            messages.error(request, "Completa los campos obligatorios.")
            return redirect(f"{request.path}?sucursal={sucursal_id_post}")

        if resultado_input not in ("RETIRADO", "AUTO"):
            messages.error(request, "Resultado inválido. Usa RETIRADO o AUTO.")
            return redirect(f"{request.path}?sucursal={sucursal_id_post}")

        estudiante = get_object_or_404(Estudiante, id=estudiante_id)
        anio = get_object_or_404(AnioLectivo, id=anio_id)
        curso = get_object_or_404(Curso, id=curso_id)

        # ✅ Importante: bloquear año activo (histórico NO)
        if anio.activo:
            messages.error(
                request,
                "No puedes registrar una promoción histórica en un año lectivo ACTIVO. "
                "Para el año activo usa Matrículas/Notas."
            )
            return redirect(f"{request.path}?sucursal={sucursal_id_post}")

        # 2) Curso debe tener orden
        if curso.orden is None:
            messages.error(request, "Este curso no tiene 'orden'. Configúralo antes.")
            return redirect(f"{request.path}?sucursal={sucursal_id_post}")

        # 3) No duplicar el mismo año lectivo
        if Promocion.objects.filter(estudiante=estudiante, anio_lectivo=anio).exists():
            messages.error(request, "Ya existe una promoción registrada para este estudiante en ese año lectivo.")
            return redirect(f"{request.path}?sucursal={sucursal_id_post}")

        # 4) No repetir curso si YA lo aprobó alguna vez
        if Promocion.objects.filter(estudiante=estudiante, curso=curso, resultado="APROBADO").exists():
            messages.error(
                request,
                f"El estudiante ya tiene {curso.nombre} como APROBADO en su historial. No se puede repetir."
            )
            return redirect(f"{request.path}?sucursal={sucursal_id_post}")

        # 5) Detalles (materias)
        filas_detalle = []
        vistos = set()

        for nom, cal in zip(asignaturas, califs):
            nom = (nom or "").strip()
            cal = (cal or "").strip()

            # ignorar fila completamente vacía
            if not nom and not cal:
                continue

            if not nom:
                messages.error(request, "Hay una fila con asignatura vacía.")
                return redirect(f"{request.path}?sucursal={sucursal_id_post}")

            key = nom.lower()
            if key in vistos:
                messages.error(request, f"Asignatura repetida: {nom}")
                return redirect(f"{request.path}?sucursal={sucursal_id_post}")
            vistos.add(key)

            if not cal:
                messages.error(request, f"Falta la calificación en: {nom}")
                return redirect(f"{request.path}?sucursal={sucursal_id_post}")

            try:
                dcal = _to_decimal_0_10(cal)
            except Exception:
                messages.error(request, f"Calificación inválida en: {nom}. Debe ser número entre 0 y 10.")
                return redirect(f"{request.path}?sucursal={sucursal_id_post}")

            filas_detalle.append((nom, dcal))

        # 6) Regla: mínimo 1 materia si no es RETIRADO
        if resultado_input != "RETIRADO" and not filas_detalle:
            messages.error(request, "Debes ingresar al menos 1 materia con calificación (excepto si es RETIRADO).")
            return redirect(f"{request.path}?sucursal={sucursal_id_post}")

        # 7) Cálculo automático (histórico)
        promedio_final = None
        resultado_final = "RETIRADO"

        if resultado_input == "RETIRADO":
            promedio_final = None
            resultado_final = "RETIRADO"
        else:
            # AUTO: promedio y aprobado/reprobado por MÍNIMO de materia (si una < 7 reprueba)
            promedio_final = _round2(sum([c for _, c in filas_detalle]) / Decimal(len(filas_detalle)))
            min_materia = min([c for _, c in filas_detalle])
            resultado_final = "APROBADO" if min_materia >= Decimal("7.00") else "REPROBADO"

        # 8) Guardar todo
        try:
            with transaction.atomic():
                promo = Promocion.objects.create(
                    estudiante=estudiante,
                    anio_lectivo=anio,
                    curso=curso,
                    resultado=resultado_final,
                    promedio_final=promedio_final,  # ✅ calculado
                    comportamiento=comportamiento,
                    observacion=observacion,
                    matricula=None,  # histórico manual
                )

                if filas_detalle:
                    PromocionDetalle.objects.bulk_create([
                        PromocionDetalle(promocion=promo, asignatura_nombre=nom, calificacion=cal)
                        for (nom, cal) in filas_detalle
                    ])

        except IntegrityError:
            messages.error(request, "Ya existe una promoción para ese estudiante en ese año lectivo.")
            return redirect(f"{request.path}?sucursal={sucursal_id_post}")
        except ValidationError as e:
            messages.error(request, f"Validación: {e}")
            return redirect(f"{request.path}?sucursal={sucursal_id_post}")
        except Exception as e:
            messages.error(request, f"No se pudo guardar la promoción: {e}")
            return redirect(f"{request.path}?sucursal={sucursal_id_post}")

        messages.success(request, "Promoción histórica registrada correctamente.")
        return redirect("promociones_editar", promocion_id=promo.id)

    return render(request, "promociones/promociones_crear.html", {
        "sucursales": sucursales,
        "sucursal_id": sucursal_id,
        "estudiantes": estudiantes,
        "anios": anios,
        "cursos": cursos,
        "RESULTADOS": [("AUTO", "Calcular automático"), ("RETIRADO", "Retirado")],
        "COMPORTAMIENTO": ["A", "B", "C", "D", "E"],
    })

def promociones_editar(request, promocion_id: int):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    promo = get_object_or_404(
        Promocion.objects.select_related("estudiante", "anio_lectivo", "curso"),
        id=promocion_id
    )

    # Si fue generada por matrícula (año actual), NO se edita aquí
    if promo.matricula_id:
        messages.error(request, "Esta promoción fue generada automáticamente por notas. No se edita como histórica.")
        return redirect("promociones_lista")

    sucursal_id = (request.GET.get("sucursal") or "").strip()

    estudiantes = Estudiante.objects.all().order_by("apellido_paterno", "apellido_materno", "nombres")
    cursos = Curso.objects.all().order_by("orden", "nombre")
    anios = AnioLectivo.objects.all().order_by("-id")

    if sucursal_id:
        estudiantes = estudiantes.filter(sucursal_id=sucursal_id)
        cursos = cursos.filter(sucursal_id=sucursal_id)

    detalles = list(promo.detalles.all().order_by("asignatura_nombre"))

    if request.method == "POST":
        estudiante_id = (request.POST.get("estudiante") or "").strip()
        anio_id = (request.POST.get("anio_lectivo") or "").strip()
        curso_id = (request.POST.get("curso") or "").strip()

        # SOLO: AUTO o RETIRADO
        resultado_input = (request.POST.get("resultado") or "").strip()

        comportamiento = (request.POST.get("comportamiento") or "").strip() or None
        observacion = (request.POST.get("observacion") or "").strip() or None

        asignaturas = request.POST.getlist("asignatura_nombre[]")
        califs = request.POST.getlist("calificacion[]")

        detalle_ids = request.POST.getlist("detalle_id[]")  # puede venir vacío en filas nuevas
        delete_ids = set(request.POST.getlist("delete_detalle[]"))  # ids a borrar

        # 1) Validación mínima
        if not (estudiante_id and anio_id and curso_id and resultado_input):
            messages.error(request, "Completa los campos obligatorios.")
            return redirect("promociones_editar", promocion_id=promo.id)

        if resultado_input not in ("RETIRADO", "AUTO"):
            messages.error(request, "Resultado inválido. Usa AUTO o RETIRADO.")
            return redirect("promociones_editar", promocion_id=promo.id)

        estudiante = get_object_or_404(Estudiante, id=estudiante_id)
        anio = get_object_or_404(AnioLectivo, id=anio_id)
        curso = get_object_or_404(Curso, id=curso_id)

        if anio.activo:
            messages.error(request, "No puedes mover una promoción histórica a un año lectivo ACTIVO.")
            return redirect("promociones_editar", promocion_id=promo.id)

        if curso.orden is None:
            messages.error(request, "Este curso no tiene 'orden'. Configúralo antes.")
            return redirect("promociones_editar", promocion_id=promo.id)

        # 2) No duplicar (estudiante + año) excluyendo esta promo
        if Promocion.objects.filter(estudiante=estudiante, anio_lectivo=anio).exclude(id=promo.id).exists():
            messages.error(request, "Ya existe otra promoción para este estudiante en ese año lectivo.")
            return redirect("promociones_editar", promocion_id=promo.id)

        # 3) No repetir curso si ya existe APROBADO en ese curso (excluyendo esta promo)
        if Promocion.objects.filter(estudiante=estudiante, curso=curso, resultado="APROBADO").exclude(id=promo.id).exists():
            messages.error(request, f"El estudiante ya tiene {curso.nombre} como APROBADO. No se puede repetir.")
            return redirect("promociones_editar", promocion_id=promo.id)

        # 4) Procesar filas finales (vivas)
        filas_vivas = []
        vistos = set()

        total = max(len(asignaturas), len(califs), len(detalle_ids))

        for i in range(total):
            det_id = (detalle_ids[i] if i < len(detalle_ids) else "").strip()
            nom = (asignaturas[i] if i < len(asignaturas) else "").strip()
            cal = (califs[i] if i < len(califs) else "").strip()

            if det_id and det_id in delete_ids:
                continue

            if not nom and not cal:
                continue

            if not nom:
                messages.error(request, "Hay una fila con asignatura vacía.")
                return redirect("promociones_editar", promocion_id=promo.id)

            key = nom.lower()
            if key in vistos:
                messages.error(request, f"Asignatura repetida: {nom}")
                return redirect("promociones_editar", promocion_id=promo.id)
            vistos.add(key)

            if resultado_input != "RETIRADO":
                if not cal:
                    messages.error(request, f"Falta la calificación en: {nom}")
                    return redirect("promociones_editar", promocion_id=promo.id)
                try:
                    dcal = _to_decimal_0_10(cal)
                except Exception:
                    messages.error(request, f"Calificación inválida en: {nom}. Debe ser 0 a 10.")
                    return redirect("promociones_editar", promocion_id=promo.id)
            else:
                # RETIRADO: no guardamos detalles
                dcal = None

            filas_vivas.append((det_id, nom, dcal))

        # 5) Regla: si AUTO -> mínimo 1 materia
        if resultado_input == "AUTO" and len(filas_vivas) == 0:
            messages.error(request, "Debes ingresar al menos 1 materia con calificación (AUTO).")
            return redirect("promociones_editar", promocion_id=promo.id)

        # 6) Calcular automático
        if resultado_input == "RETIRADO":
            promedio_final = None
            resultado_final = "RETIRADO"
        else:
            califs_validas = [c for _, _, c in filas_vivas if c is not None]
            promedio_final = _round2(sum(califs_validas) / Decimal(len(califs_validas)))
            min_materia = min(califs_validas)
            resultado_final = "APROBADO" if min_materia >= Decimal("7.00") else "REPROBADO"

        # 7) Guardar
        try:
            with transaction.atomic():
                promo.estudiante = estudiante
                promo.anio_lectivo = anio
                promo.curso = curso
                promo.resultado = resultado_final
                promo.promedio_final = promedio_final
                promo.comportamiento = comportamiento
                promo.observacion = observacion
                promo.save()

                # si RETIRADO, limpiamos todo detalle
                if resultado_input == "RETIRADO":
                    promo.detalles.all().delete()
                else:
                    # borrar marcados
                    if delete_ids:
                        promo.detalles.filter(id__in=list(delete_ids)).delete()

                    # update/create
                    for det_id, nom, dcal in filas_vivas:
                        if det_id:
                            d = promo.detalles.filter(id=det_id).first()
                            if d:
                                d.asignatura_nombre = nom
                                d.calificacion = dcal
                                d.save()
                        else:
                            PromocionDetalle.objects.create(
                                promocion=promo,
                                asignatura_nombre=nom,
                                calificacion=dcal
                            )

        except Exception as e:
            messages.error(request, f"No se pudo guardar: {e}")
            return redirect("promociones_editar", promocion_id=promo.id)

        messages.success(request, "Promoción histórica actualizada correctamente.")
        return redirect("promociones_editar", promocion_id=promo.id)

    return render(request, "promociones/promociones_editar.html", {
        "promo": promo,
        "detalles": detalles,
        "estudiantes": estudiantes,
        "anios": anios,
        "cursos": cursos,
        "sucursal_id": sucursal_id,
        "RESULTADOS": [("AUTO", "Calcular automático"), ("RETIRADO", "Retirado")],
        "COMPORTAMIENTO": ["A", "B", "C", "D", "E"],
    })
# =======================FUNCIONES PARA CONTROLAR INGRESO DE NOTAS DE LOS DOCENTES ===================================================

def _solo_secretaria(request):
    return request.session.get("usuario_rol") == "secretaria"


def _solo_docente(request):
    return request.session.get("usuario_rol") == "docente"

# Helpers de fechas

def _en_rango(hoy, ini, fin):
    if not ini or not fin:
        return False
    return ini <= hoy <= fin


def _get_anio_activo():
    return AnioLectivo.objects.filter(activo=True).order_by("-fecha_inicio").first()


def _get_periodo_anio_activo():
    """
    Retorna PeriodoNotas del año activo o None.
    Si no existe => todo bloqueado (como decidimos).
    """
    anio = _get_anio_activo()
    if not anio:
        return None, None
    periodo = PeriodoNotas.objects.filter(anio_lectivo=anio, activo=True).first()
    return anio, periodo


def _campos_habilitados_por_periodo(hoy, periodo: PeriodoNotas | None):
    """
    Devuelve dict de habilitación para t1/t2/t3/supletorio.
    Si no hay periodo => todo False.
    """
    if not periodo:
        return {"t1": False, "t2": False, "t3": False, "supletorio": False}

    return {
        "t1": _en_rango(hoy, periodo.t1_inicio, periodo.t1_fin),
        "t2": _en_rango(hoy, periodo.t2_inicio, periodo.t2_fin),
        "t3": _en_rango(hoy, periodo.t3_inicio, periodo.t3_fin),
        "supletorio": _en_rango(hoy, periodo.sup_inicio, periodo.sup_fin),
    }


def _tiene_permiso_extra(hoy, asignacion, campo, matricula=None):
    """
    Permiso extra por oficio:
    - Siempre por asignacion
    - Si matricula es None => permiso masivo (todo el paralelo)
    - Si matricula tiene valor => permiso específico a ese estudiante
    """
    qs = PermisoEdicionNotas.objects.filter(
        activo=True,
        asignacion=asignacion,
        campo=campo,
        inicio__lte=hoy,
        fin__gte=hoy,
    )
    if matricula is not None:
        # permiso específico para ese estudiante O permiso masivo (matricula null)
        return qs.filter(Q(matricula=matricula) | Q(matricula__isnull=True)).exists()

    # permiso masivo
    return qs.filter(matricula__isnull=True).exists()

# SECRETARÍA: Configurar Períodos de Notas (año activo)
def periodos_notas_config(request):
    if not _solo_secretaria(request):
        return redirect("login")

    anio, periodo = _get_periodo_anio_activo()
    if not anio:
        messages.warning(request, "No existe un Año Lectivo activo. Active uno para configurar períodos.")
        return redirect("anios_lista")

    if not periodo:
        periodo = PeriodoNotas(anio_lectivo=anio)

    def to_date(val):
        if not val:
            return None
        try:
            return datetime.strptime(val, "%Y-%m-%d").date()
        except ValueError:
            return None

    if request.method == "POST":
        periodo.t1_inicio = to_date(request.POST.get("t1_inicio"))
        periodo.t1_fin = to_date(request.POST.get("t1_fin"))
        periodo.t2_inicio = to_date(request.POST.get("t2_inicio"))
        periodo.t2_fin = to_date(request.POST.get("t2_fin"))
        periodo.t3_inicio = to_date(request.POST.get("t3_inicio"))
        periodo.t3_fin = to_date(request.POST.get("t3_fin"))
        periodo.sup_inicio = to_date(request.POST.get("sup_inicio"))
        periodo.sup_fin = to_date(request.POST.get("sup_fin"))
        periodo.activo = True
        periodo.anio_lectivo = anio

        try:
            periodo.save()  # aquí dispara full_clean()
        except ValidationError as e:
            # e.message_dict trae errores por campo (perfecto para tu clean())
            if hasattr(e, "message_dict"):
                for campo, lista in e.message_dict.items():
                    # lista puede ser list de mensajes
                    if isinstance(lista, (list, tuple)):
                        for msg in lista:
                            messages.error(request, f"{campo}: {msg}")
                    else:
                        messages.error(request, f"{campo}: {lista}")
            else:
                # error general
                messages.error(request, str(e))

            # devolvemos la misma pantalla sin guardar
            return render(request, "secretaria/periodos_notas_config.html", {
                "anio": anio,
                "periodo": periodo,
            })

        messages.success(request, f"Períodos de notas guardados para {anio.nombre}.")
        return redirect("periodos_notas_config")

    return render(request, "secretaria/periodos_notas_config.html", {
        "anio": anio,
        "periodo": periodo,
    })
# SECRETARÍA: Permisos Extra (por oficio)

def permisos_edicion_lista(request):
    if not _solo_secretaria(request):
        return redirect("login")

    q = request.GET.get("q", "").strip()
    permisos = PermisoEdicionNotas.objects.select_related(
        "asignacion__asignatura",
        "asignacion__paralelo__curso",
        "asignacion__anio_lectivo",
        "matricula__estudiante",
        "autorizado_por",
    ).order_by("-creado_en")

    if q:
        permisos = permisos.filter(
            Q(asignacion__asignatura__nombre__icontains=q) |
            Q(asignacion__paralelo__curso__nombre__icontains=q) |
            Q(matricula__estudiante__cedula__icontains=q) |
            Q(matricula__estudiante__apellido_paterno__icontains=q) |
            Q(motivo__icontains=q)
        )

    return render(request, "secretaria/permisos_edicion_lista.html", {
        "permisos": permisos[:200],
        "q": q
    })


def permisos_edicion_crear(request):
    if not _solo_secretaria(request):
        return redirect("login")

    anio = _get_anio_activo()
    if not anio:
        messages.warning(request, "No existe Año Lectivo activo.")
        return redirect("dashboard_secretaria")

    asignaciones = DocenteAsignacion.objects.select_related(
        "docente__usuario", "asignatura", "paralelo__curso", "anio_lectivo"
    ).filter(anio_lectivo=anio).order_by(
        "paralelo__curso__nombre", "paralelo__nombre", "asignatura__nombre"
    )

    if request.method == "POST":
        asignacion_id = request.POST.get("asignacion_id")
        campo = request.POST.get("campo")
        inicio = request.POST.get("inicio")
        fin = request.POST.get("fin")
        motivo = request.POST.get("motivo", "").strip()
        cedula = request.POST.get("cedula", "").strip()  # opcional, para permiso por estudiante

        # validar asignación
        asignacion = get_object_or_404(DocenteAsignacion, id=asignacion_id, anio_lectivo=anio)

        # convertir fechas
        def to_date(val):
            try:
                return datetime.strptime(val, "%Y-%m-%d").date()
            except:
                return None

        d_ini = to_date(inicio)
        d_fin = to_date(fin)

        if not d_ini or not d_fin:
            messages.error(request, "Fechas inválidas. Usa formato YYYY-MM-DD.")
            return redirect("permisos_edicion_crear")

        if d_fin < d_ini:
            messages.error(request, "La fecha fin no puede ser menor a la fecha inicio.")
            return redirect("permisos_edicion_crear")

        if campo not in ("t1", "t2", "t3", "supletorio"):
            messages.error(request, "Campo inválido.")
            return redirect("permisos_edicion_crear")

        matricula = None
        if cedula:
            # buscar matrícula dentro del paralelo y año de esa asignación
            matricula = Matricula.objects.select_related("estudiante").filter(
                anio_lectivo=asignacion.anio_lectivo,
                paralelo=asignacion.paralelo,
                estudiante__cedula=cedula
            ).first()
            if not matricula:
                messages.error(request, "No se encontró matrícula con esa cédula en ese paralelo/año.")
                return redirect("permisos_edicion_crear")

        # autorizado_por (usuario secretaria del sistema)
        usuario_secretaria = None
        try:
            usuario_secretaria = Usuario.objects.get(id=request.session.get("usuario_id"))
        except:
            usuario_secretaria = None

        PermisoEdicionNotas.objects.create(
            asignacion=asignacion,
            matricula=matricula,  # None => todo el paralelo
            campo=campo,
            inicio=d_ini,
            fin=d_fin,
            motivo=motivo if motivo else None,
            autorizado_por=usuario_secretaria if (usuario_secretaria and usuario_secretaria.rol == "secretaria") else None,
            activo=True,
        )

        messages.success(request, "Permiso de edición creado correctamente.")
        return redirect("permisos_edicion_lista")

    return render(request, "secretaria/permisos_edicion_crear.html", {
        "anio": anio,
        "asignaciones": asignaciones,
    })


def permisos_edicion_anular(request, permiso_id):
    if not _solo_secretaria(request):
        return redirect("login")

    permiso = get_object_or_404(PermisoEdicionNotas, id=permiso_id)
    permiso.activo = False
    permiso.save()

    messages.success(request, "Permiso anulado.")
    return redirect("permisos_edicion_lista")

# DOCENTE: Mis notas (vista única editable)

def mis_cursos_notas(request, asignacion_id):
    if not _solo_docente(request):
        return redirect("login")

    docente = get_object_or_404(Docente, usuario_id=request.session.get("usuario_id"))
    asignacion = get_object_or_404(DocenteAsignacion, id=asignacion_id, docente=docente)

    hoy = timezone.localdate()

    anio_activo, periodo = _get_periodo_anio_activo()
    habil = _campos_habilitados_por_periodo(hoy, periodo)

    matriculas = Matricula.objects.filter(
        paralelo=asignacion.paralelo,
        anio_lectivo=asignacion.anio_lectivo
    ).select_related("estudiante").order_by(
        "estudiante__apellido_paterno",
        "estudiante__apellido_materno",
        "estudiante__nombres"
    )

    # ========================= GUARDADO =========================
    if request.method == "POST":
        errores = []
        guardadas = 0

        def parse_nota(val, campo, estudiante_label):
            raw = (val or "").strip().replace(",", ".")
            if raw == "":
                return None, f"{estudiante_label}: Falta ingresar {campo}."

            try:
                d = Decimal(raw)
            except (InvalidOperation, ValueError):
                return None, f"{estudiante_label}: {campo} debe ser numérica (1 a 10)."

            if d < Decimal("1") or d > Decimal("10"):
                return None, f"{estudiante_label}: {campo} debe estar entre 1 y 10."

            return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), None

        with transaction.atomic():
            for m in matriculas:
                # NOTA: aquí SÍ creamos/obtenemos porque vamos a exigir llenado total
                nota, _ = Nota.objects.get_or_create(matricula=m, asignacion=asignacion)

                estudiante_label = (
                    f"{m.estudiante.apellido_paterno} "
                    f"{m.estudiante.apellido_materno} "
                    f"{m.estudiante.nombres}"
                )

                extra_t1 = _tiene_permiso_extra(hoy, asignacion, "t1", matricula=m)
                extra_t2 = _tiene_permiso_extra(hoy, asignacion, "t2", matricula=m)
                extra_t3 = _tiene_permiso_extra(hoy, asignacion, "t3", matricula=m)
                extra_sup = _tiene_permiso_extra(hoy, asignacion, "supletorio", matricula=m)

                puede_t1 = habil["t1"] or extra_t1
                puede_t2 = habil["t2"] or extra_t2
                puede_t3 = habil["t3"] or extra_t3

                cambios = False

                # ====== T1 OBLIGATORIO SI ESTÁ ABIERTO (global o por permiso) ======
                if puede_t1:
                    val, err = parse_nota(request.POST.get(f"t1_{m.id}"), "T1", estudiante_label)
                    if err:
                        errores.append(err)
                    else:
                        nota.t1 = val
                        cambios = True

                # ====== T2 OBLIGATORIO SI ESTÁ ABIERTO ======
                if puede_t2:
                    val, err = parse_nota(request.POST.get(f"t2_{m.id}"), "T2", estudiante_label)
                    if err:
                        errores.append(err)
                    else:
                        nota.t2 = val
                        cambios = True

                # ====== T3 OBLIGATORIO SI ESTÁ ABIERTO ======
                if puede_t3:
                    val, err = parse_nota(request.POST.get(f"t3_{m.id}"), "T3", estudiante_label)
                    if err:
                        errores.append(err)
                    else:
                        nota.t3 = val
                        cambios = True

                if cambios:
                    nota.save()
                    guardadas += 1

                # ====== SUPLETORIO (solo si está en SUPLETORIO y está abierto) ======
                puede_sup_ventana = habil["supletorio"] or extra_sup
                if puede_sup_ventana and nota.estado == "SUPLETORIO":
                    val, err = parse_nota(request.POST.get(f"sup_{m.id}"), "Supletorio", estudiante_label)
                    if err:
                        errores.append(err)
                    else:
                        nota.supletorio = val
                        nota.save()

            # Si hubo errores, no guardar nada
            if errores:
                transaction.set_rollback(True)
                for msg in errores[:10]:
                    messages.error(request, msg)
                if len(errores) > 10:
                    messages.error(request, f"Hay {len(errores)} estudiantes con campos faltantes/erróneos.")
                return redirect("mis_cursos_notas", asignacion_id=asignacion.id)

        messages.success(request, f"Notas guardadas correctamente ({guardadas} registros).")
        return redirect("mis_cursos_notas", asignacion_id=asignacion.id)

    # ========================= MOSTRAR =========================

    def num_input(val):
        if val is None:
            return ""
        return str(val).replace(",", ".")

    filas = []
    for m in matriculas:
        nota = Nota.objects.filter(matricula=m, asignacion=asignacion).first()

        extra_t1 = _tiene_permiso_extra(hoy, asignacion, "t1", matricula=m)
        extra_t2 = _tiene_permiso_extra(hoy, asignacion, "t2", matricula=m)
        extra_t3 = _tiene_permiso_extra(hoy, asignacion, "t3", matricula=m)
        extra_sup = _tiene_permiso_extra(hoy, asignacion, "supletorio", matricula=m)

        puede_t1 = habil["t1"] or extra_t1
        puede_t2 = habil["t2"] or extra_t2
        puede_t3 = habil["t3"] or extra_t3

        puede_sup_ventana = habil["supletorio"] or extra_sup
        puede_sup = bool(nota and nota.estado == "SUPLETORIO" and puede_sup_ventana)

        filas.append({
            "matricula": m,
            "nota": nota,
            "puede_t1": puede_t1,
            "puede_t2": puede_t2,
            "puede_t3": puede_t3,
            "puede_sup": puede_sup,
            "t1_val": num_input(getattr(nota, "t1", None)),
            "t2_val": num_input(getattr(nota, "t2", None)),
            "t3_val": num_input(getattr(nota, "t3", None)),
            "sup_val": num_input(getattr(nota, "supletorio", None)),
        })

    return render(request, "docentes/mis_cursos_notas.html", {
        "asignacion": asignacion,
        "filas": filas,
        "anio_activo": anio_activo,
        "periodo_configurado": bool(periodo),
        "hoy": hoy,
        "habil_global": habil,
    })
