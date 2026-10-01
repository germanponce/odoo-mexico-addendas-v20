from xml.dom import minidom
import argparse
import json
import os

import logging
_logger = logging.getLogger(__name__)

def getCatalogoValue(cat: str, id: str, configDict: dict):

    # Buscar la categoría y el id especificado
    try:
        targetValue = configDict.get("catDict").get(cat).get(id)
    except Exception as e:
        raise ValueError("El archivo de configuración tiene un error: {0}".format(e))

    return targetValue

def getDatosComprobante(CFDI: minidom.Document, configDict: dict):

    # Obtenemos la raiz del documento
    ComprobanteNode = CFDI.getElementsByTagName("cfdi:Comprobante")[0]
    TimbreComprobante = CFDI.getElementsByTagName('tfd:TimbreFiscalDigital')
    if TimbreComprobante:
        TimbreComprobante = TimbreComprobante[0]

    # Creamos un diccionario con los datos de la factura
    comprobante = dict()

    # Certificado, fecha, forma de pago, lugar de expedición, método de pago, moneda, no. de certificado, 
    # sello, subtotal, total, tipo de comprobante
    tipo_cambio = ComprobanteNode.getAttribute("TipoCambio")
    certificado = ComprobanteNode.getAttribute("Certificado")
    fecha = ComprobanteNode.getAttribute("Fecha")
    formaPago = ComprobanteNode.getAttribute("FormaPago")
    #Descripción de la forma de pago (Catálogo del SAT)
    formaPago =  getCatalogoValue("formaPago", formaPago, configDict)
    lugarExpedicion = ComprobanteNode.getAttribute("LugarExpedicion")
    metodoPago = ComprobanteNode.getAttribute("MetodoPago")
    # Descripción del método de pago (Catálogo del SAT)
    metodoPago = getCatalogoValue("metodoPago", metodoPago, configDict)
    moneda = ComprobanteNode.getAttribute("Moneda")
    # Descripción de la moneda (Catálogo del SAT)
    moneda = "{0} ({1})".format(getCatalogoValue("moneda", moneda, configDict), moneda)
    numCertificado = ComprobanteNode.getAttribute("NoCertificado")
    sello = ComprobanteNode.getAttribute("Sello")
    subtotal = ComprobanteNode.getAttribute("SubTotal")
    total = ComprobanteNode.getAttribute("Total")
    tipoComprobante = ComprobanteNode.getAttribute("TipoDeComprobante")
    version = ComprobanteNode.getAttribute("Version")
    if not tipo_cambio:
        tipo_cambio = 1.0
    comprobante.update(Certificado = certificado)
    comprobante.update(TipoCambio = tipo_cambio)
    comprobante.update(Fecha = fecha)
    comprobante.update(FormaPago = formaPago)
    comprobante.update(LugarExpedicion = lugarExpedicion)
    comprobante.update(MetodoPago = metodoPago)
    comprobante.update(Moneda = moneda)
    comprobante.update(NoCertificado = numCertificado)
    comprobante.update(Sello = sello)
    comprobante.update(Subtotal = subtotal)
    comprobante.update(Total = total)
    comprobante.update(TipoDeComprobante = tipoComprobante)
    comprobante.update(Version = version)

    #Serie
    #Folio
    serie = ""
    folio = ""
    try:
        serie = ComprobanteNode.getAttribute("Serie")
    except:
        serie = ""

    try:
        folio = ComprobanteNode.getAttribute("Folio")
    except:
        folio = ""

    comprobante.update(Serie = serie)
    comprobante.update(Folio = folio)

    if TimbreComprobante:
        uuid_doc = TimbreComprobante.getAttribute('UUID')
        fecha_timbrado = TimbreComprobante.getAttribute('FechaTimbrado')
        rfc_proveedor_timbrado = TimbreComprobante.getAttribute('RfcProvCertif')
        sello_cfd = TimbreComprobante.getAttribute('SelloCFD')
        no_certificado_sat = TimbreComprobante.getAttribute('NoCertificadoSAT')
        sello_sat = TimbreComprobante.getAttribute('SelloSAT')
    else:
        uuid_doc = ""
        fecha_timbrado = ""
        rfc_proveedor_timbrado = ""
        sello_cfd = ""
        no_certificado_sat = ""
        sello_sat = ""

    comprobante.update(UUID = uuid_doc)
    comprobante.update(FechaTimbrado = fecha_timbrado)
    comprobante.update(RfcProvCertif = rfc_proveedor_timbrado)
    comprobante.update(SelloCFD = sello_cfd)
    comprobante.update(NoCertificadoSAT = no_certificado_sat)
    comprobante.update(SelloSAT = sello_sat)

    # Verificamos la versión del certificado
    # if float(version) != 3.3:
    #     raise ValueError("¡BeautifyCFDI se diseñó para trabajar con certificados versión 3.3!")

    return comprobante

def getDatosEmisor(CFDI: minidom.Document, configDict: dict):

    # Obtenemos configuración del emisor
    try:
        configEmisor = configDict.get("userInfo")
    except Exception as e:
        raise ValueError("El archivo de configuración tiene un error: {0}".format(e))

    # Verificamos si el usuario quiere sobreescribir opciones
    try:
        useDefault = configEmisor.get("useDefault")
    except Exception as e:
        raise ValueError("El archivo de configuración tiene un error: {0}".format(e))

    # Obtenemos la raiz del documento
    Comprobante = CFDI.getElementsByTagName("cfdi:Comprobante")[0]
    EmisorNode = Comprobante.getElementsByTagName("cfdi:Emisor")[0]

    # Creamos un diccionario con los datos del emisor
    emisor = dict()

    # Nombre, RFC, Regimen, Domicilio y Contacto de emisor
    NombreEmisor = EmisorNode.getAttribute("Nombre")
    RfcEmisor = EmisorNode.getAttribute("Rfc")
    RegimenEmisor = EmisorNode.getAttribute("RegimenFiscal")
    # Descripción del regimen del emisor (catálogo del SAT)
    RegimenEmisor = "{0} - {1}".format(RegimenEmisor, getCatalogoValue("regimenFiscal", RegimenEmisor, configDict))
    DomicilioEmisor = ""
    ContactoEmisor = ""
    emisor.update(NombreEmisor = NombreEmisor)
    emisor.update(RfcEmisor = RfcEmisor)
    emisor.update(RegimenEmisor = RegimenEmisor)
    emisor.update(DomicilioEmisor = DomicilioEmisor)
    emisor.update(ContactoEmisor = ContactoEmisor)

    # Si el usuario quiere sobreescribir
    if useDefault is False:
        emisor.update(NombreEmisor = configEmisor["user"].get("nombre") )
        emisor.update(DomicilioEmisor = configEmisor["user"].get("domicilio") )
        emisor.update(ContactoEmisor = configEmisor["user"].get("contacto") )

    # Regresamos datos del emisor
    return emisor

def getDatosReceptor(CFDI: minidom.Document, configDict: dict):

    # Obtenemos configuración del Receptor
    try:
        configReceptor = configDict.get("clientesInfo")
    except Exception as e:
        raise ValueError("El archivo de configuración tiene un error: {0}".format(e))

    # Verificamos si el usuario quiere sobreescribir opciones
    try:
        useDefault = configReceptor.get("useDefault")
    except Exception as e:
        raise ValueError("El archivo de configuración tiene un error: {0}".format(e))

    # Obtenemos la raiz del documento
    Comprobante = CFDI.getElementsByTagName("cfdi:Comprobante")[0]
    ReceptorNode = Comprobante.getElementsByTagName("cfdi:Receptor")[0]

    # Creamos un diccionario con los datos del Receptor
    receptor = dict()

    # Nombre, RFC, Regimen, Domicilio y Contacto de receptor
    NombreReceptor = ReceptorNode.getAttribute("Nombre")
    RfcReceptor = ReceptorNode.getAttribute("Rfc")
    UsoReceptor = ReceptorNode.getAttribute("UsoCFDI")
    RegimenReceptor = ReceptorNode.getAttribute("RegimenFiscalReceptor")
    print ("## RegimenReceptor ", RegimenReceptor)
    DomicilioFiscalReceptor = ReceptorNode.getAttribute("DomicilioFiscalReceptor")
    #Descripción uso CFDI del uso de CFDI
    UsoReceptor = "{0} - {1}".format(UsoReceptor, getCatalogoValue("usoCFDI", UsoReceptor, configDict))
    DomicilioReceptor = ""
    receptor.update(NombreReceptor = NombreReceptor)
    receptor.update(RfcReceptor = RfcReceptor)
    receptor.update(UsoReceptor = UsoReceptor)
    receptor.update(DomicilioReceptor = DomicilioReceptor)
    receptor.update(RegimenReceptor = RegimenReceptor)
    receptor.update(DomicilioFiscalReceptor = DomicilioFiscalReceptor)

    # Si el usuario quiere sobreescribir
    if useDefault is False:
        if configReceptor["clientesDict"].get(RfcReceptor, None) is None:
            _logger.info("\nNo se encontró información para el cliente con RFC {0}".format(RfcReceptor))
        else:
            NombreReceptor = configReceptor["clientesDict"].get(RfcReceptor, {}).get("nombre", "")
            DomicilioReceptor = configReceptor["clientesDict"].get(RfcReceptor, {}).get("domicilio", "")
            receptor.update(NombreReceptor = NombreReceptor)
            receptor.update(DomicilioReceptor = DomicilioReceptor)

    # Regresamos datos del receptor
    return receptor

def getConceptos(CFDI: minidom.Document, configDict: dict):
    
    # Obtenemos configuración de los conceptos
    try:
        configConceptos = configDict.get("conceptosInfo")
    except Exception as e:
        raise ValueError("El archivo de configuración tiene un error: {0}".format(e))

    # Verificamos si el usuario quiere sobreescribir datos de los conceptos
    try:
        useDefault = configConceptos.get("useDefault")
    except Exception as e:
        raise ValueError("El archivo de configuración tiene un error: {0}".format(e))

    # Obtenemos la raiz del documento y el nodo de conceptos
    Comprobante = CFDI.getElementsByTagName("cfdi:Comprobante")[0]
    ConceptosNode = Comprobante.getElementsByTagName("cfdi:Conceptos")[0]

    # Obtenemos una lista de los conceptos registrados
    ConceptosList = ConceptosNode.getElementsByTagName("cfdi:Concepto")

    # Creamos una lista con los datos de los conceptos
    conceptos = list()

    # Iteramos por cada concepto
    for ConceptoNode in ConceptosList:

        # Creamos un diccionario para contener información del concepto
        concepto = dict()

        # Obtenemos cantidad, claveProd, claveUnidad, Descripción, Importe, Valor Unitario
        cantidad = ConceptoNode.getAttribute("Cantidad")
        claveProd = ConceptoNode.getAttribute("ClaveProdServ")
        unidad = ConceptoNode.getAttribute("Unidad")
        claveUnidad = ConceptoNode.getAttribute("ClaveUnidad")
        #Descripción de unidad (de acuerdo con el catálogo del SAT)
        #claveUnidad = "{0} ({1})".format(getCatalogoValue("claveUnidad", claveUnidad, configDict), claveUnidad)
        descripcion = ConceptoNode.getAttribute("Descripcion")
        importe = ConceptoNode.getAttribute("Importe")
        valorUnitario = ConceptoNode.getAttribute("ValorUnitario")
        concepto.update(Cantidad = cantidad)
        concepto.update(ClaveProdServ = claveProd)
        concepto.update(Unidad = unidad)
        concepto.update(ClaveUnidad = claveUnidad)
        concepto.update(Descripcion = descripcion)
        concepto.update(Importe = importe)
        concepto.update(ValorUnitario = valorUnitario)

        # Si el usuario quiere sobreescribir
        if useDefault is False:
            if configConceptos["conceptosDict"].get(claveProd, None) is None:
                _logger.info("\nNo se encontró información para el producto/servicio con clave {0}".format(claveProd))
            else:
                claveProd = configConceptos["conceptosDict"].get(claveProd, {}).get("miClave", "")
                claveUnidad = configConceptos["conceptosDict"].get(claveProd, {}).get("miUnidad", "")
                descripcion = configConceptos["conceptosDict"].get(claveProd, {}).get("miDescripcion", "")
                concepto.update(ClaveProdServ = claveProd)
                concepto.update(ClaveUnidad = claveUnidad)
                concepto.update(Descripcion = descripcion)

        # Creamos una lista de impuesto para contener información de los impuestos
        impuestos = dict()

        # Obtenemos datos de los impuestos
        if ConceptoNode.getElementsByTagName("cfdi:Impuestos"):
            ImpuestosNode = ConceptoNode.getElementsByTagName("cfdi:Impuestos")[0]
        else:
            ImpuestosNode = []

        # Creamos una lista de traslados y retenciones        
        if ImpuestosNode:
            trasladosList = ImpuestosNode.getElementsByTagName("cfdi:Traslado")
            retencionesList = ImpuestosNode.getElementsByTagName("cfdi:Retencion")
        else:
            trasladosList = []
            retencionesList = []

        # Iteramos por cada impuesto en traslado y retención
        for ImpuestoNode in (trasladosList + retencionesList):

            #Creamos un diccionario para contener la información del impuesto
            impuesto = dict()

            #Obtenemos tipo de impuesto y tipo de factor
            tipoImpuesto = ImpuestoNode.tagName.split(":")[1]
            factor = ImpuestoNode.getAttribute("TipoFactor")

            #Obtenemos impuesto, tasa, base e importe
            impuestoNombre = ImpuestoNode.getAttribute("Impuesto")
            tasaCuota = ImpuestoNode.getAttribute("TasaOCuota")
            base = ImpuestoNode.getAttribute("Base")
            importe = ImpuestoNode.getAttribute("Importe")
            impuesto.update(TipoImpuesto = tipoImpuesto)
            impuesto.update(TipoFactor = factor)
            impuesto.update(Impuesto = impuestoNombre)
            impuesto.update(TasaOCuota = tasaCuota)
            impuesto.update(Base = base)
            impuesto.update(Importe = importe)

            #Agregamos este impuesto a la lista
            impuestos.update({"{0}:{1}".format(tipoImpuesto, impuestoNombre): impuesto})

        # Agregamos el diccionario de impuestos al diccionario de concepto
        concepto.update(Impuestos = impuestos)

        # Agregamos el concepto al diccionario de conceptos
        conceptos.append(concepto)

    return conceptos

def BeautifyCFDI(xml_string = None, out = 'pdf', configPath = "./config.json"):
    # Abrimos configPath
    configPath = os.fsencode(configPath)
    # try:
    with open(configPath, "r") as configFile:
        configFileContents = configFile.read()
        configDict = json.loads(configFileContents)
    # except Exception as e:
    #     raise ValueError("Ocurrió un error al abrir el archivo de configuración especificado: {0}".format(e))

    # Abrimos el cfdi
    CFDI = minidom.parseString(xml_string)

    # Extraemos datos del comprobante
    comprobante = getDatosComprobante(CFDI, configDict)
    # Extraemos datos del emisor
    emisor = getDatosEmisor(CFDI, configDict)
    # Extraemos datos del receptor
    receptor = getDatosReceptor(CFDI, configDict)
    # Extraemos datos de los conceptos
    conceptos = getConceptos(CFDI, configDict)

    # print ("### emisor >>>>>>>>>> ",emisor)
    # print ("### receptor >>>>>>>>>> ",receptor)
    # print ("### conceptos >>>>>>>>>> ",conceptos)
    # print ("### comprobante >>>>>>>>>> ",comprobante)

    result = {
                'emisor': emisor,
                'receptor': receptor,
                'conceptos': conceptos,
                'comprobante': comprobante,
            }
    return result

def parseArguments():
    """Esta función analiza los argumentos proporcionados por el usuario desde la línea de comandos y los pasa a la función
    principal (BeautifyCFDI)."""

    # Creamos una instancia de ArgumentParser
    main_parser = argparse.ArgumentParser()
    # Definimos una descripción del porgrama
    main_parser.description = "BeautifyCFDI: imprimibles estéticos de CFDIs."

    # Agregamos argumentos
    # fileDirGroup es un conjunto de argumentos mutuamente exclusivos (o archivo o directorio)
    fileDirGroup = main_parser.add_argument_group("Argumentos posicionales")
    fileDirGroup.add_argument("target", type = str,
                              help = "Ruta del archivo XML con el CFDI. Si el usuario suministra un directorio, entonces todos los XML con CFDI válidos serán usados.")
    # optionsGroup
    optGroup = main_parser.add_argument_group("Opciones")
    optGroup.add_argument("-c", "--config", type = str, default = './config.json', dest = "configFile",
                          help = "Ruta del archivo de configuración. Por default = ./config.json")
    optGroup.add_argument("-o", "--output", type = str, default = 'pdf', choices = ['pdf', 'html', 'docx'],
                          dest = "out", help = "Formato de salida. Por el momento, BeautifyCFDI soporta pdf, html y docx.")

    # Parseamos argumentos
    parsed_args = main_parser.parse_args()

    # Mandamos los argumentos a la función
    BeautifyCFDI(parsed_args.target, parsed_args.out, parsed_args.configFile)


# El código se ejecuta directamente
if __name__ == "__main__":
    parseArguments()
