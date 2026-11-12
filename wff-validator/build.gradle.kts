plugins {
    alias(libs.plugins.kotlin.jvm)
    application
}

dependencies {
    // Xerces build with XML Schema 1.1 support (the WFF XSD uses 1.1 features
    // such as maxOccurs > 1 inside <xs:all>, which libxml2/JDK validators reject).
    implementation(variantOf(libs.xerces.xsd11) { classifier("xml-schema-1.1") })
    // Optional (in the POM) but required at runtime for XSD 1.1 assertions.
    runtimeOnly("org.exist-db.thirdparty.org.eclipse.wst.xml:xpath2:1.2.0")
    runtimeOnly("edu.princeton.cup:java-cup:10k")
}

application {
    mainClass.set("org.neteinstein.dashface.validator.MainKt")
}
