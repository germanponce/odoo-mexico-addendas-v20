"""Migration script — l10n_mx_xml_massive_download 19.0.46.7

Limpia residuos historicos al actualizar desde versiones anteriores:

1) Grupo viejo `group_access_xml_sat_user` (xmlid de versiones <= 17.0.13.0
   instaladas por antiguos forks de Cosal). El grupo nuevo es
   `group_l10n_mx_xml_sat_user`. Si el viejo existe, migramos sus usuarios
   al nuevo y borramos el grupo + sus accesos/reglas/xmlid.

2) Modulos fantasma con sufijo `.PAUSADO` o similar — residuos de operaciones
   manuales de deploy (renombrado de symlink). Borramos el record huerfano.

3) Regeneramos la vista dinamica `res.users.groups` via ORM para que no
   queden referencias `in_group_<id_borrado>` cacheadas.

Se ejecuta automaticamente en `odoo-bin -u l10n_mx_xml_massive_download`.
Idempotente: corre sin hacer nada si no hay residuos.
"""
import logging
from odoo.api import Environment, SUPERUSER_ID

_logger = logging.getLogger(__name__)

LEGACY_GROUP_XMLID = "l10n_mx_xml_massive_download.group_access_xml_sat_user"
NEW_GROUP_XMLID = "l10n_mx_xml_massive_download.group_l10n_mx_xml_sat_user"


def migrate(cr, version):
    """Args provistos por Odoo:
       cr: psycopg2 cursor
       version: version desde la que se migra (str o None si fresh install)
    """
    if not version:
        return  # Fresh install: nada que limpiar

    _logger.info(
        "anfepi: post-migrate 19.0.46.7 — limpiando residuos historicos "
        "(migrando desde %s)", version,
    )
    env = Environment(cr, SUPERUSER_ID, {})
    _migrate_legacy_group(env)
    _cleanup_pausado_modules(env)
    _regenerate_user_groups_view(env)


def _migrate_legacy_group(env):
    """Migra usuarios del grupo viejo al nuevo y borra el viejo."""
    old_group = env.ref(LEGACY_GROUP_XMLID, raise_if_not_found=False)
    if not old_group:
        _logger.info("anfepi: no hay grupo legacy 'group_access_xml_sat_user' — skip")
        return

    new_group = env.ref(NEW_GROUP_XMLID, raise_if_not_found=False)
    if not new_group:
        _logger.warning(
            "anfepi: grupo legacy %s existe pero el nuevo (%s) no. "
            "Algo raro paso en el upgrade. Skip limpieza.",
            old_group.id, NEW_GROUP_XMLID,
        )
        return

    users = old_group.users
    _logger.info(
        "anfepi: migrando %s usuarios del grupo legacy %s -> nuevo %s",
        len(users), old_group.id, new_group.id,
    )
    if users:
        # Asignar nuevo grupo a los usuarios que no lo tengan, quitar el viejo.
        # write({'groups_id': [(4, new.id), (3, old.id)]}) en cada usuario es atomico.
        new_group.users = [(4, u.id) for u in users]
        old_group.users = [(5, 0, 0)]  # clear M2M

    # Borrar accesos, reglas e implied groups que apunten al viejo.
    env.cr.execute("DELETE FROM ir_model_access WHERE group_id = %s", (old_group.id,))
    env.cr.execute("DELETE FROM rule_group_rel WHERE group_id = %s", (old_group.id,))
    env.cr.execute(
        "DELETE FROM res_groups_implied_rel WHERE gid = %s OR hid = %s",
        (old_group.id, old_group.id),
    )

    # Borrar xmlid (sino unlink falla por proteccion)
    env.cr.execute(
        """
        DELETE FROM ir_model_data
        WHERE model = 'res.groups' AND res_id = %s
          AND module = 'l10n_mx_xml_massive_download'
          AND name = 'group_access_xml_sat_user'
        """,
        (old_group.id,),
    )

    # Finalmente borrar el grupo via ORM (dispara validaciones de integridad)
    old_id = old_group.id
    try:
        old_group.sudo().unlink()
    except Exception as e:
        # Fallback a SQL directo si hay referencias raras
        _logger.warning("anfepi: unlink ORM fallo (%s); fallback a SQL DELETE", e)
        env.cr.execute("DELETE FROM res_groups WHERE id = %s", (old_id,))
    _logger.info("anfepi: grupo legacy %s borrado", old_id)


def _cleanup_pausado_modules(env):
    """Borra records ir.module.module con sufijo '.PAUSADO' que quedan tras
    operaciones manuales de deploy (renombrar symlinks). Solo borra si state
    es 'uninstalled'."""
    fantasmas = env["ir.module.module"].search([
        ("name", "like", "%.PAUSADO"),
        ("state", "=", "uninstalled"),
    ])
    if fantasmas:
        names = fantasmas.mapped("name")
        fantasmas.sudo().unlink()
        _logger.info("anfepi: borrados %s modulos fantasma: %s", len(names), names)


def _regenerate_user_groups_view(env):
    """Regenera la vista dinamica `res.users.groups` (la del form de res.users
    con todos los checkboxes de groups). Si dejamos referencias a in_group_X
    de un grupo borrado, el UI tira error de OWL.
    """
    try:
        env["res.groups"]._update_user_groups_view()
        _logger.info("anfepi: vista res.users.groups regenerada")
    except Exception as e:
        _logger.warning("anfepi: regen vista user groups fallo: %s", e)
