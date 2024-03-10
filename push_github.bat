@ECHO OFF
cls
git add *
git rm -r "diemdanhkhuonmat/dataset/*.*"
git rm -r "diemdanhkhuonmat/classifier.xml"
git commit -m "Update"
git push
echo "DONE!"
PAUSE