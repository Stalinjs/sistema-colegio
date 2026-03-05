from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from .models import Matricula, Nota, Docente, DocenteAsignacion, Promocion, PromocionDetalle, Estudiante, AnioLectivo, Curso
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.contrib import messages

# =========================
# HELPERS
# =========================

def _round2(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _cualitativa(promedio: Decimal | None) -> str:
    if promedio is None:
        return "—"

    p = Decimal(promedio)

    if p <= Decimal("4.00"):
        return "No alcanza los aprendizajes requeridos."
    if Decimal("4.01") <= p <= Decimal("6.99"):
        return "Está próximo a alcanzar los aprendizajes requeridos."
    if Decimal("7.00") <= p <= Decimal("8.99"):
        return "Alcanza los aprendizajes requeridos."
    if Decimal("9.00") <= p <= Decimal("10.00"):
        return "Domina los aprendizajes requeridos."

    return "—"


def _comportamiento_texto(letra: str | None) -> str:
    letra = (letra or "").upper().strip()
    mapa = {
        "A": "Lidera el cumplimiento de los compromisos establecidos para la sana convivencia social.",
        "B": "Cumple con los compromisos establecidos para la sana convivencia social.",
        "C": "Falla con los compromisos establecidos para la sana convivencia social.",
        "D": "—",
        "E": "—",
    }
    return mapa.get(letra, "—")


def _siguiente_curso_por_orden(curso_actual: Curso | None) -> str:
    """
    Devuelve el nombre del siguiente curso basado en Curso.orden.
    """
    if not curso_actual or curso_actual.orden is None:
        return "SIGUIENTE GRADO (pendiente de configurar)"

    siguiente = (
        Curso.objects
        .filter(sucursal_id=curso_actual.sucursal_id, orden=curso_actual.orden + 1)
        .first()
    )
    return siguiente.nombre if siguiente else "SIGUIENTE GRADO (pendiente de configurar)"


def _get_regimen_extension_desde_curso(curso: Curso):
    # En tu BD: Sucursal.ubicacion = régimen (Costa/Sierra)
    regimen = (curso.sucursal.ubicacion or "").upper()
    extension = curso.sucursal.nombre
    return regimen, extension


# =========================
# BUSCAR (MATRÍCULA + HISTÓRICO)
# =========================

def promocion_buscar(request):
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    q = request.GET.get("q", "").strip()
    resultados = []

    if q:
        # 1) Matrículas (normalmente año activo)
        matriculas = (
            Matricula.objects.select_related(
                "estudiante",
                "paralelo__curso__sucursal",
                "anio_lectivo",
            )
            .filter(
                Q(estudiante__cedula__icontains=q)
                | Q(estudiante__nombres__icontains=q)
                | Q(estudiante__apellido_paterno__icontains=q)
                | Q(estudiante__apellido_materno__icontains=q)
            )
            .order_by("-anio_lectivo__nombre", "estudiante__apellido_paterno")[:50]
        )

        for m in matriculas:
            resultados.append({
                "tipo": "matricula",
                "anio": m.anio_lectivo.nombre,
                "estudiante": m.estudiante,
                "curso": m.paralelo.curso,
                "obj_id": m.id,
            })

        # 2) Promociones históricas (sin matrícula)
        promociones = (
            Promocion.objects.select_related(
                "estudiante",
                "anio_lectivo",
                "curso__sucursal",
            )
            .filter(
                Q(estudiante__cedula__icontains=q)
                | Q(estudiante__nombres__icontains=q)
                | Q(estudiante__apellido_paterno__icontains=q)
                | Q(estudiante__apellido_materno__icontains=q)
            )
            .order_by("-anio_lectivo__nombre", "estudiante__apellido_paterno")[:50]
        )

        for p in promociones:
            resultados.append({
                "tipo": "promocion",
                "anio": p.anio_lectivo.nombre,
                "estudiante": p.estudiante,
                "curso": p.curso,
                "obj_id": p.id,
            })

        # Orden final: año desc, apellido asc
        resultados.sort(key=lambda r: (r["anio"], r["estudiante"].apellido_paterno), reverse=True)

    return render(
        request,
        "reportes/promocion_buscar.html",
        {"q": q, "resultados": resultados},
    )


# =========================
# CERTIFICADO DESDE MATRÍCULA (NOTAS)
# =========================

def promocion_certificado(request, matricula_id: int):
    """
    Certificado cuando existe matrícula (normalmente año activo).
    Si las notas no están completas (promedio NULL), intenta caer a Promocion histórica (si existe).
    """
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    matricula = get_object_or_404(
        Matricula.objects.select_related(
            "estudiante",
            "paralelo__curso__sucursal",
            "anio_lectivo",
        ),
        id=matricula_id
    )

    # comportamiento por GET: ?comp=A/B/C...
    comp_get = (request.GET.get("comp") or "").upper().strip()

    # si no viene por GET, usa el guardado en la promo
    comportamiento = comp_get  # en año actual se elige por GET
    puede_emitir = bool(comportamiento)

    comportamiento_texto = (
        _comportamiento_texto(comportamiento)
        if puede_emitir
        else "Debe seleccionar un comportamiento para emitir el certificado."
    )


    promo = None  # la usamos luego si toca histórico

    # 1) Intentamos sacar por NOTAS (año actual)
    notas = (
        Nota.objects.select_related("asignacion__asignatura")
        .filter(matricula=matricula)
        .order_by("asignacion__asignatura__nombre")
    )

    if notas.exists():
        # Año actual: si no viene comp por GET, que lo seleccione en pantalla (como ya lo haces)
        if not comportamiento:
            puede_emitir = False

    else:
        # Histórico
        promo = Promocion.objects.filter(
            estudiante=matricula.estudiante,
            anio_lectivo=matricula.anio_lectivo,
        ).first()

        # ✅ si NO viene comp por GET, usa el comportamiento guardado en promoción histórica
        if (not comportamiento) and promo and promo.comportamiento:
            comportamiento = promo.comportamiento
            puede_emitir = True

    comportamiento_texto = (
        _comportamiento_texto(comportamiento)
        if puede_emitir
        else "Debe seleccionar un comportamiento para emitir el certificado."
    )

    filas = []
    promedios = []

    # ✅ Solo usamos notas que ya tengan PROMEDIO FINAL calculado
    notas = (
        Nota.objects.select_related("asignacion__asignatura")
        .filter(matricula=matricula, promedio__isnull=False)
        .order_by("asignacion__asignatura__nombre")
    )

    if notas.exists():
        for n in notas:
            prom = Decimal(n.promedio)
            promedios.append(prom)

            filas.append({
                "asignatura": n.asignacion.asignatura.nombre,
                "cuantitativa": prom,
                "cualitativa": _cualitativa(prom),
            })

        promedio_general = _round2(sum(promedios) / Decimal(len(promedios))) if promedios else None
        origen = "NOTAS"

    else:
        # fallback a histórico si existe promoción cargada para ese estudiante+año
        promo = Promocion.objects.filter(
            estudiante=matricula.estudiante,
            anio_lectivo=matricula.anio_lectivo,
        ).prefetch_related("detalles").first()

        if promo:
            detalles = promo.detalles.all().order_by("asignatura_nombre")
            for d in detalles:
                filas.append({
                    "asignatura": d.asignatura_nombre,
                    "cuantitativa": d.calificacion,
                    "cualitativa": _cualitativa(Decimal(d.calificacion)) if d.calificacion is not None else "—",
                })
            promedio_general = promo.promedio_final
            origen = "HISTORICO"
        else:
            promedio_general = None
            origen = "SIN_DATOS"
            messages.warning(
                request,
                "Este estudiante no tiene promedios finales calculados en notas y tampoco tiene promoción histórica cargada."
            )

    promedio_cualitativo = _cualitativa(Decimal(promedio_general)) if promedio_general is not None else "—"
    promovido = (promedio_general is not None and Decimal(promedio_general) >= Decimal("7.00"))

    siguiente_grado = _siguiente_curso_por_orden(matricula.paralelo.curso) if promovido else "—"

    regimen, extension = _get_regimen_extension_desde_curso(matricula.paralelo.curso)

    context = {
        "matricula": matricula,  # tu template ya lo usa
        "filas": filas,
        "promedio_general": promedio_general,
        "promedio_cualitativo": promedio_cualitativo,
        "anio_lectivo_nombre": matricula.anio_lectivo.nombre,
        "curso_nombre": matricula.paralelo.curso.nombre,
        "comportamiento": comportamiento if puede_emitir else "—",
        "comportamiento_texto": comportamiento_texto,
        "puede_emitir": puede_emitir,
        "promovido": promovido,
        "siguiente_grado": siguiente_grado,
        "hoy": timezone.localdate(),
        "regimen": regimen,
        "extension": extension,
        "origen": origen,  # por si quieres mostrar una muestra: NOTAS/HISTORICO
        "es_historico": False,
    }
    return render(request, "reportes/certificado_promocion.html", context)


# =========================
# CERTIFICADO HISTÓRICO (SIN MATRÍCULA)
# =========================

def promocion_certificado_historico(request, promocion_id: int):
    """
    Certificado cuando NO hay matrícula (años anteriores sin T1/T2/T3).
    Usa Promocion + PromocionDetalle.
    """
    if request.session.get("usuario_rol") != "secretaria":
        return redirect("login")

    promo = get_object_or_404(
        Promocion.objects.select_related("estudiante", "anio_lectivo", "curso__sucursal"),
        id=promocion_id
    )

    comp_get = (request.GET.get("comp") or "").upper().strip()
    comp_db = (promo.comportamiento or "").upper().strip()

    comportamiento = comp_get or comp_db   # ✅ prioridad: GET, si no hay -> BD
    puede_emitir = bool(comportamiento)

    comportamiento_texto = (
        _comportamiento_texto(comportamiento)
        if puede_emitir
        else "Debe seleccionar un comportamiento para emitir el certificado."
    )


    detalles = (
        PromocionDetalle.objects
        .filter(promocion=promo)
        .order_by("asignatura_nombre")  # si luego pides orden malla, aquí cambiamos
    )

    filas = []
    for d in detalles:
        filas.append({
            "asignatura": d.asignatura_nombre,
            "cuantitativa": d.calificacion,
            "cualitativa": _cualitativa(Decimal(d.calificacion)) if d.calificacion is not None else "—",
        })

    promedio_general = promo.promedio_final
    promedio_cualitativo = _cualitativa(Decimal(promedio_general)) if promedio_general is not None else "—"

    # promovido: usa resultado si está; si no, usa promedio
    if promo.resultado == "APROBADO":
        promovido = True
    elif promo.resultado == "REPROBADO":
        promovido = False
    else:
        promovido = (promedio_general is not None and Decimal(promedio_general) >= Decimal("7.00"))

    siguiente_grado = _siguiente_curso_por_orden(promo.curso) if promovido else "—"

    regimen, extension = _get_regimen_extension_desde_curso(promo.curso)

    # IMPORTANTE: tu template actual recibe "matricula".
    # Aquí mandamos matricula=None y además mandamos estudiante/curso/anio para que lo uses si hace falta.
    context = {
        "matricula": None,
        "estudiante": promo.estudiante,
        "anio_lectivo": promo.anio_lectivo,
        "curso": promo.curso,
        "anio_lectivo_nombre": promo.anio_lectivo.nombre,
        "curso_nombre": promo.curso.nombre,

        "filas": filas,
        "promedio_general": promedio_general,
        "promedio_cualitativo": promedio_cualitativo,
        "comportamiento": comportamiento if puede_emitir else "—",
        "comportamiento_texto": comportamiento_texto,
        "puede_emitir": puede_emitir,
        "promovido": promovido,
        "siguiente_grado": siguiente_grado,
        "hoy": timezone.localdate(),
        "regimen": regimen,
        "extension": extension,
        "origen": "HISTORICO",
        "es_historico": True,
        "promo": promo,
    }
    return render(request, "reportes/certificado_promocion.html", context)
# ==================================================================================================================

# =================================== NOMINA DE ESTUDIANTES ==========================

def nomina_notas_print(request, asignacion_id):
    # Solo docente
    if request.session.get("usuario_rol") != "docente":
        return redirect("login")

    docente = get_object_or_404(Docente, usuario_id=request.session.get("usuario_id"))
    asignacion = get_object_or_404(DocenteAsignacion, id=asignacion_id, docente=docente)

    # Matrículas del paralelo/año de esa asignación
    matriculas = Matricula.objects.filter(
        paralelo=asignacion.paralelo,
        anio_lectivo=asignacion.anio_lectivo
    ).select_related("estudiante").order_by(
        "estudiante__apellido_paterno", "estudiante__apellido_materno", "estudiante__nombres"
    )

    # Notas de esa asignación (más eficiente: 1 query)
    notas_qs = Nota.objects.filter(asignacion=asignacion, matricula__in=matriculas).select_related("matricula")
    notas_map = {n.matricula_id: n for n in notas_qs}

    filas = []
    for m in matriculas:
        filas.append({
            "matricula": m,
            "nota": notas_map.get(m.id)
        })

    hoy = timezone.localdate()

    return render(request, "docentes/nomina_notas_print.html", {
        "asignacion": asignacion,
        "filas": filas,
        "hoy": hoy,
        "docente": docente,
    })
