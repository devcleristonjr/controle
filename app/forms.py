from __future__ import annotations

from decimal import Decimal

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import BooleanField, DecimalField, HiddenField, PasswordField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional


PUBLIC_IMAGE_FIELD_LABEL = "Foto do local"
PUBLIC_OBSERVACOES_LABEL = "Observ" + "ações"
PUBLIC_IMAGE_VALIDATION_MESSAGE = "Formato de imagem inválido. Use JPG, JPEG, PNG ou WEBP."
MATERIAL_UNIT_CHOICES = [
    ("unidade", "Unidade"),
    ("pacote", "Pacote"),
    ("caixa", "Caixa"),
    ("metro", "Metro"),
    ("rolo", "Rolo"),
]
OCCURRENCE_TYPE_CHOICES = [
    ("DANIFICADO", "Danificou / Quebrou"),
    ("PERDIDO", "Foi perdido"),
    ("RETIRADO", "Foi retirado"),
    ("REPOSICAO_NECESSARIA", "Precisa de reposição"),
    ("OUTRO", "Outro"),
]


class UsuarioForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(), Length(max=120)])
    email = StringField("E-mail", validators=[DataRequired(), Email(), Length(max=180)])
    perfil = SelectField(
        "Perfil",
        choices=[("ADMIN", "Administrador"), ("OPERADOR", "Operador"), ("VISUALIZADOR", "Visualizador")],
        validators=[DataRequired()],
    )
    ativo = BooleanField("Ativo", default=True)
    senha = PasswordField("Senha", validators=[Optional(), Length(min=6, max=255)])


class CadastroUsuarioForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(), Length(max=120)])
    email = StringField("E-mail", validators=[DataRequired(), Email(), Length(max=180)])
    senha = PasswordField("Senha", validators=[DataRequired(), Length(min=6, max=255)])
    confirmar_senha = PasswordField("Confirmar senha", validators=[DataRequired(), Length(min=6, max=255)])


class TerritorioForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(), Length(max=180)])
    codigo = StringField("Código", validators=[Optional(), Length(max=50)])
    ativo = BooleanField("Ativo", default=True)


class MunicipioForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(), Length(max=180)])
    territorio_id = SelectField("Território", coerce=int, validators=[DataRequired()])
    codigo_ibge = StringField("Código IBGE", validators=[Optional(), Length(max=20)])
    latitude = StringField("Latitude", validators=[Optional()])
    longitude = StringField("Longitude", validators=[Optional()])
    ativo = BooleanField("Ativo", default=True)


class LoginForm(FlaskForm):
    email = StringField("E-mail", validators=[DataRequired(), Email(), Length(max=180)])
    password = PasswordField("Senha", validators=[DataRequired(), Length(min=6, max=255)])
    remember_me = BooleanField("Lembrar-me")


class MaterialForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(), Length(max=180)])
    quantidade_total = DecimalField(
        "Estoque total",
        places=2,
        rounding=None,
        validators=[DataRequired(), NumberRange(min=Decimal("0"))],
    )
    unidade = SelectField("Unidade de medida", choices=MATERIAL_UNIT_CHOICES, validators=[DataRequired()])
    descricao = TextAreaField("Descrição", validators=[Optional(), Length(max=2000)])
    ativo = BooleanField("Ativo", default=True)


class PontoEstoqueForm(FlaskForm):
    nome = StringField("Nome do local", validators=[DataRequired(), Length(max=180)])
    municipio_id = SelectField("Município", coerce=int, validators=[DataRequired()])
    endereco = StringField("Endereço", validators=[Optional(), Length(max=255)])
    coordenadas = StringField("Coordenadas do Google Maps", validators=[Optional()])
    latitude = StringField("Latitude", validators=[Optional()])
    longitude = StringField("Longitude", validators=[Optional()])
    responsavel_nome = StringField("Nome do responsável", validators=[Optional(), Length(max=180)])
    responsavel_telefone = StringField("Telefone", validators=[Optional(), Length(max=30)])
    responsavel_whatsapp = StringField("WhatsApp", validators=[Optional(), Length(max=30)])
    foto = FileField(
        "Foto do local",
        validators=[
            Optional(),
            FileAllowed(["jpg", "jpeg", "png", "webp"], "Formato de imagem invalido. Use JPG, JPEG, PNG ou WEBP."),
        ],
    )
    observacoes = TextAreaField(PUBLIC_OBSERVACOES_LABEL, validators=[Optional(), Length(max=4000)])
    ativo = BooleanField("Ativo", default=True)


class EstoqueMovimentacaoForm(FlaskForm):
    material_id = SelectField("Material", coerce=int, validators=[DataRequired()])
    tipo = SelectField(
        "Tipo",
        choices=[("ENTRADA", "Entrada"), ("SAIDA", "Saída"), ("AJUSTE", "Ajuste")],
        validators=[DataRequired()],
    )
    quantidade = DecimalField(
        "Quantidade",
        places=2,
        rounding=None,
        validators=[DataRequired(), NumberRange(min=Decimal("0.01"))],
    )
    observacao = TextAreaField("Observação", validators=[Optional(), Length(max=4000)])


class ColetaEstoqueForm(FlaskForm):
    step = HiddenField(default="input")
    foto_path = HiddenField(validators=[Optional()])
    observacoes = TextAreaField(PUBLIC_OBSERVACOES_LABEL, validators=[Optional(), Length(max=4000)])
    latitude = HiddenField(validators=[Optional()])
    longitude = HiddenField(validators=[Optional()])
    foto = FileField(
        "Foto do estoque",
        validators=[
            Optional(),
            FileAllowed(["jpg", "jpeg", "png", "webp"], "Formato de imagem inválido. Use JPG, JPEG, PNG ou WEBP."),
        ],
    )


class ColetaPublicCadastroForm(FlaskForm):
    nome_local = StringField(
        "Nome do local",
        validators=[DataRequired(), Length(max=180)],
        render_kw={"required": False},
    )
    municipio_id = SelectField(
        "Município",
        coerce=int,
        validators=[DataRequired()],
        render_kw={"required": False},
    )
    endereco = StringField("Endereço", validators=[Optional(), Length(max=255)])
    responsavel_nome = StringField(
        "Nome do responsável",
        validators=[DataRequired(), Length(max=180)],
        render_kw={"required": False},
    )
    responsavel_whatsapp = StringField(
        "WhatsApp",
        validators=[DataRequired(), Length(max=30)],
        render_kw={"required": False},
    )
    coletor_nome = StringField(
        "Nome de quem está enviando o formulário",
        validators=[DataRequired(), Length(max=180)],
        render_kw={"required": False},
    )
    observacoes = TextAreaField(PUBLIC_OBSERVACOES_LABEL, validators=[Optional(), Length(max=4000)])
    latitude = HiddenField(validators=[Optional()])
    longitude = HiddenField(validators=[Optional()])
    foto_path = HiddenField(validators=[Optional()])
    foto = FileField(
        PUBLIC_IMAGE_FIELD_LABEL,
        validators=[
            Optional(),
            FileAllowed(["jpg", "jpeg", "png", "webp"], PUBLIC_IMAGE_VALIDATION_MESSAGE),
        ],
    )


class ColetaPublicAtualizacaoForm(FlaskForm):
    coletor_nome = StringField(
        "Nome de quem está realizando esta atualização",
        validators=[DataRequired(), Length(max=180)],
        render_kw={"required": False},
    )
    observacoes = TextAreaField(PUBLIC_OBSERVACOES_LABEL, validators=[Optional(), Length(max=4000)])
    foto_path = HiddenField(validators=[Optional()])
    foto = FileField(
        PUBLIC_IMAGE_FIELD_LABEL,
        validators=[
            Optional(),
            FileAllowed(["jpg", "jpeg", "png", "webp"], PUBLIC_IMAGE_VALIDATION_MESSAGE),
        ],
    )


class AlocacaoPontoMaterialForm(FlaskForm):
    material_id = SelectField("Material", coerce=int, validators=[DataRequired()])
    quantidade_alocada = DecimalField(
        "Quantidade para alocar",
        places=2,
        rounding=None,
        validators=[DataRequired(), NumberRange(min=Decimal("0.01"))],
    )
    localizador = StringField("Localizador do ponto", validators=[Optional(), Length(max=180)])
    responsavel_alocacao = StringField("Responsável pela alocação", validators=[Optional(), Length(max=180)])
    observacoes = TextAreaField("Observações", validators=[Optional(), Length(max=4000)])


class OcorrenciaAlocacaoForm(FlaskForm):
    tipo = SelectField("O que aconteceu com este material neste ponto?", choices=OCCURRENCE_TYPE_CHOICES, validators=[DataRequired()])
    quantidade_afetada = DecimalField(
        "Quantidade envolvida",
        places=2,
        rounding=None,
        validators=[DataRequired(), NumberRange(min=Decimal("0.01"))],
    )
    descricao = TextAreaField("Observação", validators=[Optional(), Length(max=4000)])


class ReposicaoAlocacaoForm(FlaskForm):
    quantidade_reposta = DecimalField(
        "Quantidade reposta",
        places=2,
        rounding=None,
        validators=[DataRequired(), NumberRange(min=Decimal("0.01"))],
    )
    observacao = TextAreaField("Observação", validators=[Optional(), Length(max=4000)])
