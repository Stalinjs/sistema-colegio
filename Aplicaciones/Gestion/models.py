from django.db import models
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.apps import apps

def validar_cedula_ec(cedula: str) -> bool:
    """
    Valida cédula ecuatoriana (10 dígitos) con:
    - Provincia 01..24
    - 3er dígito 0..5
    - Dígito verificador (módulo 10)
    """
    if cedula is None:
        return False

    c = str(cedula).strip()

    # Debe ser solo números y 10 dígitos
    if len(c) != 10 or not c.isdigit():
        return False

    # Evitar casos tipo 0000000000, 1111111111,
    if c == c[0] * 10:
        return False

    provincia = int(c[0:2])
    if provincia < 1 or provincia > 24:
        return False

    tercer = int(c[2])
    if tercer < 0 or tercer > 5:
        return False

    # Algoritmo del dígito verificador
    coef = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    suma = 0
    for i in range(9):
        val = int(c[i]) * coef[i]
        if val >= 10:
            val -= 9
        suma += val

    verificador_calculado = (10 - (suma % 10)) % 10
    verificador_real = int(c[9])

    return verificador_calculado == verificador_real

# ============================================================
# NORMALIZACIÓN GLOBAL: MAYÚSCULAS (y correo en minúsculas)
# ============================================================
class UpperCaseMixin(models.Model):
    """
    Convierte a MAYÚSCULAS los campos listados en UPPERCASE_FIELDS
    y a minúsculas los campos listados en LOWERCASE_FIELDS (ej: correo).
    Además:
    - strip() al inicio/fin
    - colapsa espacios internos a uno solo
    """
    UPPERCASE_FIELDS = []
    LOWERCASE_FIELDS = []

    class Meta:
        abstract = True

    def _norm_upper(self, s: str) -> str:
        return " ".join(s.strip().upper().split())

    def _norm_lower(self, s: str) -> str:
        return s.strip().lower()

    def normalize_fields(self):
        for f in getattr(self, "UPPERCASE_FIELDS", []):
            val = getattr(self, f, None)
            if isinstance(val, str) and val is not None:
                setattr(self, f, self._norm_upper(val))

        for f in getattr(self, "LOWERCASE_FIELDS", []):
            val = getattr(self, f, None)
            if isinstance(val, str) and val is not None:
                setattr(self, f, self._norm_lower(val))

    def save(self, *args, **kwargs):
        self.normalize_fields()
        super().save(*args, **kwargs)


# ============================================================
# SUCURSALES
# ============================================================
class Sucursal(UpperCaseMixin, models.Model):
    REGIMEN_CHOICES = (
        ("Costa", "Costa"),
        ("Sierra", "Sierra"),
    )
    UPPERCASE_FIELDS = ["nombre"]  # ubicacion es choice (no hace falta)

    nombre = models.CharField(max_length=100, unique=True)
    ubicacion = models.CharField(max_length=20, choices=REGIMEN_CHOICES, blank=True, null=True)
    activa = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


# ============================================================
# ESPECIALIDADES
# ============================================================
class Especialidad(UpperCaseMixin, models.Model):
    UPPERCASE_FIELDS = ["nombre", "descripcion"]

    nombre = models.CharField(max_length=150, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    activa = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


# ============================================================
# CURSOS
# ============================================================
class Curso(UpperCaseMixin, models.Model):
    UPPERCASE_FIELDS = ["nombre", "nivel"]

    nombre = models.CharField(max_length=150)
    especialidad = models.ForeignKey(Especialidad, on_delete=models.PROTECT, null=True, blank=True)
    nivel = models.CharField(max_length=150)
    orden = models.PositiveSmallIntegerField()
    sucursal = models.ForeignKey(Sucursal, on_delete=models.PROTECT)

    class Meta:
        unique_together = ('nombre', 'especialidad', 'sucursal')

    def clean(self):
        errors = {}
        if self.orden is None:
            errors["orden"] = _("El campo 'orden' es obligatorio (ej: 8, 9, 10...).")
        else:
            if self.orden < 1 or self.orden > 20:
                errors["orden"] = _("El 'orden' debe estar entre 1 y 20.")

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.normalize_fields()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        esp = self.especialidad.nombre if self.especialidad else "GENERAL"
        return f"{self.nombre} - {esp} - {self.sucursal.nombre}"
# ============================================================
# PARALELOS
# ============================================================
class Paralelo(UpperCaseMixin, models.Model):
    UPPERCASE_FIELDS = ["nombre"]

    curso = models.ForeignKey(Curso, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=10) 

    class Meta:
        unique_together = ('curso', 'nombre')

    def __str__(self):
        return f"{self.curso} - Paralelo {self.nombre}"


# ============================================================
# AÑO LECTIVO
# ============================================================
class AnioLectivo(UpperCaseMixin, models.Model):
    UPPERCASE_FIELDS = ["nombre"]

    nombre = models.CharField(max_length=20, unique=True)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    activo = models.BooleanField(default=False)

    def __str__(self):
        return self.nombre


# ============================================================
# USUARIOS
# ============================================================
class Usuario(UpperCaseMixin, models.Model):
    ROLES = (
        ('admin', 'Administrador'),
        ('secretaria', 'Secretaria'),
        ('docente', 'Docente'),
    )

    UPPERCASE_FIELDS = ["nombres", "apellido_paterno", "apellido_materno", "direccion"]
    LOWERCASE_FIELDS = ["correo"]  # correo en minúsculas

    cedula = models.CharField(max_length=10, unique=True)
    nombres = models.CharField(max_length=200)
    apellido_paterno = models.CharField(max_length=200)
    apellido_materno = models.CharField(max_length=200)
    correo = models.EmailField(max_length=200, blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    direccion = models.CharField(max_length=250, blank=True, null=True)
    rol = models.CharField(max_length=20, choices=ROLES)
    password = models.CharField(max_length=255)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def clean(self):
        errors = {}

        if self.cedula:
            self.cedula = self.cedula.strip()

        if not validar_cedula_ec(self.cedula):
            errors["cedula"] = _("Cédula inválida. Verifique que sea una cédula ecuatoriana real de 10 dígitos.")

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.normalize_fields()
        self.full_clean()
        return super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.cedula} - {self.nombres} {self.apellido_paterno}"


# ============================================================
# DOCENTES
# ============================================================
class Docente(UpperCaseMixin, models.Model):
    UPPERCASE_FIELDS = ["titulo"]

    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE)
    titulo = models.CharField(max_length=150, blank=True, null=True)

    def __str__(self):
        nombres = f"{self.usuario.nombres} {self.usuario.apellido_paterno}"
        return f"Docente: {nombres}"


# ============================================================
# ESTUDIANTES
# ============================================================
class Estudiante(UpperCaseMixin, models.Model):
    UPPERCASE_FIELDS = ["nombres", "apellido_paterno", "apellido_materno", "direccion"]

    cedula = models.CharField(max_length=10, unique=True)
    nombres = models.CharField(max_length=200)
    apellido_paterno = models.CharField(max_length=200)
    apellido_materno = models.CharField(max_length=200)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    telefono = models.CharField(max_length=15, blank=True, null=True)
    direccion = models.CharField(max_length=200, blank=True, null=True)
    sucursal = models.ForeignKey(Sucursal, on_delete=models.PROTECT)

    def clean(self):
        errors = {}

        # --- CÉDULA ---
        if self.cedula:
            self.cedula = self.cedula.strip()

        if not validar_cedula_ec(self.cedula):
            errors["cedula"] = _("Cédula inválida. Verifique que sea una cédula ecuatoriana real de 10 dígitos.")

        if self.fecha_nacimiento:
            hoy = date.today()

            if self.fecha_nacimiento >= hoy:
                errors["fecha_nacimiento"] = _("La fecha de nacimiento no puede ser hoy ni futura.")

            edad = hoy.year - self.fecha_nacimiento.year - (
                (hoy.month, hoy.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
            )

            EDAD_MIN = 11
            EDAD_MAX = 90

            if edad < EDAD_MIN:
                errors["fecha_nacimiento"] = _(f"El estudiante debe tener al menos {EDAD_MIN} años.")
            elif edad > EDAD_MAX:
                errors["fecha_nacimiento"] = _(f"La edad del estudiante no puede superar {EDAD_MAX} años.")

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.normalize_fields()
        self.full_clean()
        return super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.cedula} - {self.nombres}"


# ============================================================
# ASIGNATURAS
# ============================================================
class Asignatura(UpperCaseMixin, models.Model):
    UPPERCASE_FIELDS = ["nombre"]

    nombre = models.CharField(max_length=150)
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('nombre', 'curso')

    def __str__(self):
        return f"{self.nombre} - {self.curso}"


# ============================================================
# DOCENTE_ASIGNACION
# ============================================================
class DocenteAsignacion(models.Model):
    docente = models.ForeignKey(Docente, on_delete=models.CASCADE)
    asignatura = models.ForeignKey(Asignatura, on_delete=models.CASCADE)
    paralelo = models.ForeignKey(Paralelo, on_delete=models.CASCADE)
    anio_lectivo = models.ForeignKey(AnioLectivo, on_delete=models.PROTECT)

    class Meta:
        unique_together = ('docente', 'asignatura', 'paralelo', 'anio_lectivo')

    def __str__(self):
        return f"{self.docente} - {self.asignatura} - {self.paralelo}"


# ============================================================
# MATRICULAS
# ============================================================
class Matricula(UpperCaseMixin, models.Model):
    UPPERCASE_FIELDS = ["observaciones"]

    TIPO_PROGRAMA = [
        ("adultos", "Personas adultas"),
        ("nna", "Niños y adolescentes"),
        ("intensivo", "Intensivo"),
    ]

    ESTADOS = [
        ("MATRICULADO", "Matriculado"),
        ("RENUNCIA", "Renuncia voluntaria"),
        ("DESERTOR", "Desertor"),
    ]

    JORNADAS = [
        ("MATUTINA", "Matutina"),
        ("VESPERTINA", "Vespertina"),
        ("NOCTURNA", "Nocturna"),
    ]

    TEMPORALIDAD = [
        ("INTENSIVA", "Intensiva"),
        ("NO_INTENSIVA", "No intensiva"),
    ]

    estudiante = models.ForeignKey("Estudiante", on_delete=models.CASCADE)
    paralelo = models.ForeignKey("Paralelo", on_delete=models.PROTECT)
    anio_lectivo = models.ForeignKey("AnioLectivo", on_delete=models.PROTECT)

    tipo_programa = models.CharField(max_length=20, choices=TIPO_PROGRAMA)
    jornada = models.CharField(max_length=20, choices=JORNADAS, null=True, blank=True)
    temporalidad = models.CharField(max_length=20, choices=TEMPORALIDAD, null=True, blank=True)
    estado_estudiante = models.CharField(max_length=20, choices=ESTADOS, null=True, blank=True)
    observaciones = models.TextField(null=True, blank=True)

    fecha = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = ("estudiante", "anio_lectivo")

    def clean(self):
        errors = {}

        if not self.estudiante_id:
            errors["estudiante"] = _("Selecciona un estudiante.")
        if not self.paralelo_id:
            errors["paralelo"] = _("Selecciona un paralelo.")
        if not self.anio_lectivo_id:
            errors["anio_lectivo"] = _("Selecciona un año lectivo.")

        if errors:
            raise ValidationError(errors)

        # 1) Coherencia de sucursal
        if self.estudiante.sucursal_id != self.paralelo.curso.sucursal_id:
            errors["paralelo"] = _("El paralelo pertenece a otra sucursal distinta a la del estudiante.")

        # 2) Año lectivo activo
        if not self.anio_lectivo.activo:
            errors["anio_lectivo"] = _("No puedes matricular en un año lectivo inactivo.")

        # 3) Campos obligatorios reales
        if not self.jornada:
            errors["jornada"] = _("La jornada es obligatoria.")
        if not self.temporalidad:
            errors["temporalidad"] = _("La temporalidad es obligatoria.")
        if not self.estado_estudiante:
            errors["estado_estudiante"] = _("El estado del estudiante es obligatorio.")

        # 4) Validación académica por orden
        curso_nuevo = self.paralelo.curso
        if curso_nuevo.orden is None:
            errors["paralelo"] = _("El curso seleccionado no tiene 'orden' configurado. Configúralo primero.")
        else:
            Promocion = apps.get_model(self._meta.app_label, "Promocion")

            ult_aprob = (
                Promocion.objects
                .filter(estudiante_id=self.estudiante_id, resultado="APROBADO", curso__orden__isnull=False)
                .select_related("curso")
                .order_by("-curso__orden")
                .first()
            )

            if ult_aprob:
                orden_max = ult_aprob.curso.orden
                orden_nuevo = curso_nuevo.orden

                if orden_nuevo <= orden_max:
                    errors["paralelo"] = _(
                        f"No se puede matricular en {curso_nuevo.nombre}. "
                        f"El estudiante ya aprobó {ult_aprob.curso.nombre} (orden {orden_max})."
                    )
                elif orden_nuevo > (orden_max + 1):
                    errors["paralelo"] = _(
                        f"No se puede saltar de nivel. "
                        f"Último aprobado: {ult_aprob.curso.nombre}. "
                        f"Debe matricularse en el siguiente curso (orden {orden_max + 1})."
                    )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Normaliza antes de validar
        self.normalize_fields()
        self.full_clean()
        return super().save(*args, **kwargs)


# ============================================================
# PROMOCION
# ============================================================
class Promocion(UpperCaseMixin, models.Model):
    UPPERCASE_FIELDS = ["observacion"]

    RESULTADOS = [
        ("APROBADO", "Aprobado"),
        ("REPROBADO", "Reprobado"),
        ("RETIRADO", "Retirado"),
    ]

    COMPORTAMIENTO = [
        ("A", "A"),
        ("B", "B"),
        ("C", "C"),
        ("D", "D"),
        ("E", "E"),
    ]

    estudiante = models.ForeignKey("Estudiante", on_delete=models.CASCADE)
    anio_lectivo = models.ForeignKey("AnioLectivo", on_delete=models.PROTECT)
    curso = models.ForeignKey("Curso", on_delete=models.PROTECT)

    matricula = models.ForeignKey(
        "Matricula",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="promocion_generada",
    )

    promedio_final = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    resultado = models.CharField(max_length=20, choices=RESULTADOS)
    comportamiento = models.CharField(max_length=1, choices=COMPORTAMIENTO, null=True, blank=True)
    observacion = models.CharField(max_length=255, null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("estudiante", "anio_lectivo")
        indexes = [
            models.Index(fields=["estudiante", "anio_lectivo"]),
            models.Index(fields=["estudiante", "resultado"]),
            models.Index(fields=["curso"]),
        ]

    def clean(self):
        errors = {}

        if self.matricula_id:
            if self.matricula.estudiante_id != self.estudiante_id:
                errors["matricula"] = _("La matrícula no pertenece a este estudiante.")
            if self.matricula.anio_lectivo_id != self.anio_lectivo_id:
                errors["anio_lectivo"] = _("El año lectivo no coincide con la matrícula.")
            if self.matricula.paralelo.curso_id != self.curso_id:
                errors["curso"] = _("El curso no coincide con el curso de la matrícula.")

        if self.curso_id and self.curso.orden is None:
            errors["curso"] = _("Este curso no tiene 'orden' configurado. Configúralo para controlar niveles.")

        if self.estudiante_id and self.curso_id:
            ya_aprobo_ese = (
                Promocion.objects
                .filter(estudiante_id=self.estudiante_id, curso_id=self.curso_id, resultado="APROBADO")
                .exclude(pk=self.pk)
                .exists()
            )
            if ya_aprobo_ese:
                errors["curso"] = _("El estudiante ya tiene ese curso como APROBADO en su historial. No se puede repetir.")

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Normaliza antes de validar
        self.normalize_fields()

        if self.matricula_id is None and self.resultado != "RETIRADO":
            if self.promedio_final is not None:
                p = Decimal(self.promedio_final)
                if p < Decimal("0") or p > Decimal("10"):
                    raise ValidationError({"promedio_final": _("El promedio final debe estar entre 0 y 10.")})

        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.estudiante.cedula} - {self.anio_lectivo.nombre} - {self.curso.nombre} - {self.resultado}"


# ============================================================
# PROMOCION DETALLE
# ============================================================
class PromocionDetalle(UpperCaseMixin, models.Model):
    UPPERCASE_FIELDS = ["asignatura_nombre"]

    promocion = models.ForeignKey("Promocion", on_delete=models.CASCADE, related_name="detalles")
    asignatura_nombre = models.CharField(max_length=150)
    calificacion = models.DecimalField(max_digits=4, decimal_places=2)

    class Meta:
        unique_together = ("promocion", "asignatura_nombre")
        ordering = ["asignatura_nombre"]

    def clean(self):
        errors = {}
        if self.calificacion is None:
            errors["calificacion"] = _("La calificación es obligatoria.")
        else:
            p = Decimal(self.calificacion)
            if p < Decimal("0") or p > Decimal("10"):
                errors["calificacion"] = _("La calificación debe estar entre 0 y 10.")
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # ✅ Normaliza antes de validar
        self.normalize_fields()
        self.full_clean()
        return super().save(*args, **kwargs)


# ============================================================
# NOTAS
# ============================================================
class Nota(models.Model):
    matricula = models.ForeignKey(Matricula, on_delete=models.CASCADE)
    asignacion = models.ForeignKey("DocenteAsignacion", on_delete=models.CASCADE)
    t1 = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    t2 = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    t3 = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    supletorio = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)

    promedio = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    estado = models.CharField(max_length=50, null=True, blank=True)

    def _round2(self, x: Decimal) -> Decimal:
        return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def save(self, *args, **kwargs):
        if self.t1 is None or self.t2 is None or self.t3 is None:
            self.promedio = None
            self.estado = None
            return super().save(*args, **kwargs)

        base = (Decimal(self.t1) + Decimal(self.t2) + Decimal(self.t3)) / Decimal("3")
        base = self._round2(base)

        if base >= Decimal("7.00"):
            self.promedio = base
            self.estado = "APROBADO"
        elif base >= Decimal("4.00"):
            if self.supletorio is not None and Decimal(self.supletorio) >= Decimal("7.00"):
                self.promedio = Decimal("7.00")
                self.estado = "APROBADO"
            else:
                self.promedio = base
                self.estado = "SUPLETORIO"
        else:
            self.promedio = base
            self.estado = "REPROBADO"

        return super().save(*args, **kwargs)


# ============================================================
# PERÍODOS DE NOTAS
# ============================================================
class PeriodoNotas(models.Model):
    anio_lectivo = models.OneToOneField(AnioLectivo, on_delete=models.PROTECT, related_name="periodo_notas")

    t1_inicio = models.DateField(null=True, blank=True)
    t1_fin = models.DateField(null=True, blank=True)

    t2_inicio = models.DateField(null=True, blank=True)
    t2_fin = models.DateField(null=True, blank=True)

    t3_inicio = models.DateField(null=True, blank=True)
    t3_fin = models.DateField(null=True, blank=True)

    sup_inicio = models.DateField(null=True, blank=True)
    sup_fin = models.DateField(null=True, blank=True)

    activo = models.BooleanField(default=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def clean(self):
        errors = {}

        pares = [
            ("t1_inicio", "t1_fin", "T1"),
            ("t2_inicio", "t2_fin", "T2"),
            ("t3_inicio", "t3_fin", "T3"),
            ("sup_inicio", "sup_fin", "Supletorio"),
        ]

        for a, b, label in pares:
            ini = getattr(self, a)
            fin = getattr(self, b)

            if (ini and not fin) or (fin and not ini):
                errors[a] = _(f"En {label} debes ingresar fecha inicio y fecha fin.")
                errors[b] = _(f"En {label} debes ingresar fecha inicio y fecha fin.")
                continue

            if ini and fin and fin < ini:
                errors[b] = _(f"En {label}, la fecha fin no puede ser anterior a la fecha inicio.")

        def completo(ini, fin):
            return ini is not None and fin is not None

        t1_ok = completo(self.t1_inicio, self.t1_fin)
        t2_ok = completo(self.t2_inicio, self.t2_fin)
        t3_ok = completo(self.t3_inicio, self.t3_fin)
        sup_ok = completo(self.sup_inicio, self.sup_fin)

        if t2_ok and not t1_ok:
            errors["t1_inicio"] = _("Debes configurar primero T1 antes de T2.")
            errors["t1_fin"] = _("Debes configurar primero T1 antes de T2.")

        if t3_ok and not t2_ok:
            errors["t2_inicio"] = _("Debes configurar primero T2 antes de T3.")
            errors["t2_fin"] = _("Debes configurar primero T2 antes de T3.")

        if sup_ok and not t3_ok:
            errors["t3_inicio"] = _("Debes configurar primero T3 antes de Supletorio.")
            errors["t3_fin"] = _("Debes configurar primero T3 antes de Supletorio.")

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"PeriodoNotas {self.anio_lectivo.nombre}"


# ============================================================
# PERMISOS EXTRA DE EDICIÓN DE NOTAS
# ============================================================
class PermisoEdicionNotas(UpperCaseMixin, models.Model):
    UPPERCASE_FIELDS = ["motivo"]

    CAMPOS = (
        ("t1", "T1"),
        ("t2", "T2"),
        ("t3", "T3"),
        ("supletorio", "Supletorio"),
    )

    asignacion = models.ForeignKey("DocenteAsignacion", on_delete=models.CASCADE, related_name="permisos_edicion")
    matricula = models.ForeignKey("Matricula", on_delete=models.CASCADE, null=True, blank=True, related_name="permisos_edicion")

    campo = models.CharField(max_length=20, choices=CAMPOS)

    inicio = models.DateField()
    fin = models.DateField()

    motivo = models.CharField(max_length=255, blank=True, null=True)
    autorizado_por = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="permisos_otorgados",
        limit_choices_to={"rol": "secretaria"},
    )

    activo = models.BooleanField(default=True)

    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        target = f" - {self.matricula.estudiante.cedula}" if self.matricula_id else " - TODO EL PARALELO"
        return f"Permiso {self.campo} ({self.inicio} a {self.fin}){target}"

    class Meta:
        verbose_name = "Permiso de Edición de Notas"
        verbose_name_plural = "Permisos de Edición de Notas"
        indexes = [
            models.Index(fields=["asignacion", "campo", "activo"]),
            models.Index(fields=["matricula", "campo", "activo"]),
        ]