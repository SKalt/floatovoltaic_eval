#! /usr/bin/env bash
if [ -f dams/major_us_dams_2006.geojson ];
then echo "nice, geojson already made";
else ogr2ogr -f "GeoJSON"              \
    -t_srs "EPSG:4326"              \
    dams/major_us_dams_2006.geojson \
    dams/dams00x020.shp;
fi;

tippecanoe -o "major_us_dams_2006.mbtiles" \
  -f                                       \
  -z 14                                    \
  -Z 3                                     \
  -Bg                                      \
  -rg                                      \
  dams/major_us_dams_2006.geojson
