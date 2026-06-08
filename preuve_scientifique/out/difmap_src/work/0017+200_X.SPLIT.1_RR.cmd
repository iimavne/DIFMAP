observe 0017+200_X.SPLIT.1
select RR
mapsize 512,0.1
invert
wdmap 0017+200_X.SPLIT.1_RR_dirty.fits
wbeam 0017+200_X.SPLIT.1_RR_beam.fits
delwin
addwin -2.0,2.0,-2.0,2.0
addwin -10.0,-6.0,4.0,8.0
save 0017+200_X.SPLIT.1_RR_state
clean 100,0.05
wdmap 0017+200_X.SPLIT.1_RR_residual.fits
restore
wmap 0017+200_X.SPLIT.1_RR_clean.fits
wobs 0017+200_X.SPLIT.1_RR_uv.fits
quit
