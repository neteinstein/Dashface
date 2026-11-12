package com.neteinstein.dashface.validator

import java.io.File
import javax.xml.transform.stream.StreamSource
import javax.xml.validation.SchemaFactory
import org.xml.sax.ErrorHandler
import org.xml.sax.SAXParseException

/**
 * Validates a Watch Face Format document against the official XSD.
 *
 * Usage: Main <watchface.xsd> <watchface.xml>
 * Exits with status 1 and prints every problem if the document is invalid.
 */
fun main(args: Array<String>) {
    require(args.size == 2) { "Usage: <watchface.xsd> <watchface.xml>" }
    val (xsd, xml) = args.map(::File)

    val factory = SchemaFactory.newInstance(
        "http://www.w3.org/XML/XMLSchema/v1.1",
        "org.apache.xerces.jaxp.validation.XMLSchema11Factory",
        null,
    )
    val schema = factory.newSchema(StreamSource(xsd))

    val problems = mutableListOf<String>()
    val validator = schema.newValidator().apply {
        errorHandler = object : ErrorHandler {
            override fun warning(e: SAXParseException) = Unit
            override fun error(e: SAXParseException) { problems += format(e) }
            override fun fatalError(e: SAXParseException) { problems += format(e) }
        }
    }
    validator.validate(StreamSource(xml))

    if (problems.isEmpty()) {
        println("OK: ${xml.name} is valid against ${xsd.parentFile.name}/${xsd.name}")
    } else {
        problems.forEach(System.err::println)
        System.err.println("FAILED: ${problems.size} problem(s) in ${xml.name}")
        kotlin.system.exitProcess(1)
    }
}

private fun format(e: SAXParseException) = "line ${e.lineNumber}:${e.columnNumber}: ${e.message}"
