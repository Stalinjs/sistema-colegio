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

    estudiante = matricula.estudiante
    curso = matricula.paralelo.curso
    anio_lectivo = matricula.anio_lectivo
    comp_get = (request.GET.get("comp") or "").upper().strip()
    comportamiento = comp_get
    puede_emitir = bool(comportamiento)
    notas = (
        Nota.objects.select_related("asignacion__asignatura")
        .filter(matricula=matricula, promedio__isnull=False)
        .order_by("asignacion__asignatura__nombre")
    )

    filas = []
    promedios = []
    origen = "SIN_DATOS"

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
        promo = Promocion.objects.filter(
            estudiante=estudiante,
            anio_lectivo=anio_lectivo,
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

            if not comportamiento and promo.comportamiento:
                comportamiento = promo.comportamiento
                puede_emitir = True

        else:
            promedio_general = None
            messages.warning(
                request,
                "Este estudiante no tiene promedios en notas ni promoción histórica."
            )

    comportamiento_texto = (
        _comportamiento_texto(comportamiento)
        if puede_emitir
        else "Debe seleccionar un comportamiento para emitir el certificado."
    )

    promedio_cualitativo = (
        _cualitativa(Decimal(promedio_general))
        if promedio_general is not None else "—"
    )

    promovido = (
        promedio_general is not None and Decimal(promedio_general) >= Decimal("7.00")
    )

    siguiente_grado = (
        _siguiente_curso_por_orden(curso) if promovido else "—"
    )

    regimen, extension = _get_regimen_extension_desde_curso(curso)
    context = {
        "matricula": matricula,
        "estudiante": estudiante,
        "anio_lectivo": anio_lectivo,
        "curso": curso,

        "filas": filas,
        "promedio_general": promedio_general,
        "promedio_cualitativo": promedio_cualitativo,

        "anio_lectivo_nombre": anio_lectivo.nombre,
        "curso_nombre": curso.nombre,

        "comportamiento": comportamiento if puede_emitir else "—",
        "comportamiento_texto": comportamiento_texto,
        "puede_emitir": puede_emitir,

        "promovido": promovido,
        "siguiente_grado": siguiente_grado,

        "hoy": timezone.localdate(),
        "regimen": regimen,
        "extension": extension,

        "origen": origen,
        "es_historico": (origen == "HISTORICO"),
    }

    return render(request, "reportes/certificado_promocion.html", context)

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

    comportamiento = comp_get or comp_db  
    puede_emitir = bool(comportamiento)

    comportamiento_texto = (
        _comportamiento_texto(comportamiento)
        if puede_emitir
        else "Debe seleccionar un comportamiento para emitir el certificado."
    )


    detalles = (
        PromocionDetalle.objects
        .filter(promocion=promo)
        .order_by("asignatura_nombre") 
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

    if promo.resultado == "APROBADO":
        promovido = True
    elif promo.resultado == "REPROBADO":
        promovido = False
    else:
        promovido = (promedio_general is not None and Decimal(promedio_general) >= Decimal("7.00"))

    siguiente_grado = _siguiente_curso_por_orden(promo.curso) if promovido else "—"

    regimen, extension = _get_regimen_extension_desde_curso(promo.curso)
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

# =================================== NOMINA DE ESTUDIANTES ==========================

def nomina_notas_print(request, asignacion_id):
    if request.session.get("usuario_rol") != "docente":
        return redirect("login")

    docente = get_object_or_404(Docente, usuario_id=request.session.get("usuario_id"))
    asignacion = get_object_or_404(DocenteAsignacion, id=asignacion_id, docente=docente)

    matriculas = Matricula.objects.filter(
        paralelo=asignacion.paralelo,
        anio_lectivo=asignacion.anio_lectivo
    ).select_related("estudiante").order_by(
        "estudiante__apellido_paterno", "estudiante__apellido_materno", "estudiante__nombres"
    )
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
