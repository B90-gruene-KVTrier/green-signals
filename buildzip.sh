# !/bin/sh

# gather the files required for public release
# put them into a ZIP
#
# for now we only need the two Python scripts

DISTPATH="./out/gruene-signale"
FILEMASK="*.py"

rm -rf out
mkdir -p $DISTPATH

cp $FILEMASK $DISTPATH

cd ./out
zip -r gruene-signale gruene-signale/$FILEMASK
cd ..
