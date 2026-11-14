MGS MOLA Topography Derived Data Bundle

This bundle contains MGS MOLA derived data migrated from the PDS3 volumes 
MGS-M-MOLA-5-MEGDR-L3-V1.0 and the partial PDS3 volume MGS-M-MOLA-5-SHADR-V1.0. 
This data set contains map products derived from altimetry data 
observations acquired by the Mars Global Surveyor (MGS) Mars Orbiter Laser 
Altimeter (MOLA) instrument as well as coefficients and related data for a 
spherical harmonic model of the shape of Mars.

The bundle contains the following collections:

- Six MEGDR data collections with the following directory names:
        - meg004: MEGDR Map Data - 4 pixels per degree
        - meg016: MEGDR Map Data - 16 pixels per degree
        - meg032: MEGDR Map Data - 32 pixels per degree
        - meg064: MEGDR Map Data - 64 pixels per degree
        - meg128: MEGDR Map Data - 128 pixels per degree
        - polar: MEGDR Polar Map Data
- One SHADR data collection in the shadr directory. 
- Two document collections located in the catalog and document directories.
  The PDS3 catalog files are located in the catalog directory 
- The SIS and a User's Guide for reading map data into ENVI and ARCGIS is
  in the document directory.
- One miscellaneous collection for the PDS3 index file located in the index
  directory.

Each product in this bundle is described by a PDS4 label in a separate file
with the same name as the file described by the label but with the extension
XML. PDS4 labels are XML (eXtended Markup Language) files that conform to the
PDS4 Information Model XML schema at 
https://pds.nasa.gov/pds4/schema/released/. The PDS4 labels are best viewed
in an XML-aware text editor, and may be used by software that can manipulate
XML documents.

Note: The PDS4 version of this dataset excludes certain PDS3 directories and 
products that are no longer relevant given the inclusion of PDS4 documentation. 
For user convenience, the original PDS3 labels for the data products have been 
retained within the PDS4 bundle. All data products have also been given PDS4 
labels.

This bundle was created and archived by the Geosciences Node of the Planetary
Data System. Questions about this bundle may be directed to
geosci@wunder.wustl.edu.