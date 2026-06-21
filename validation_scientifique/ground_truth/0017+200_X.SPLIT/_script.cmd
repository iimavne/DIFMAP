observe 0017+200_X.SPLIT.1
select RR
mapsize 512,0.1
invert
wdmap 0017+200_X.SPLIT_dirty.fits
wobs 0017+200_X.SPLIT_uv.fits
clean 500,0.05
restore
wmap 0017+200_X.SPLIT_clean.fits
selfcal
invert
clean 500,0.05
restore
wmap 0017+200_X.SPLIT_clean_selfcal.fits
wobs 0017+200_X.SPLIT_uv_after_sc.fits
quit
