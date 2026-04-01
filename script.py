from difmap_wrapper.observation import Observation
from difmap_wrapper.session import DifmapSession
from difmap_wrapper.imaging import DifmapImager

with DifmapSession() as session:
    session.observe("tests/test_data/0003-066_X.SPLIT.1")
    obs = Observation(session)
    img = DifmapImager()
    
    obs.select()
    
    # --- LA MAGIE EST ICI ---
    obs.radplot()                # Vérifier les données avant l'image
    img.uvweight(bin_size=2.0)   # Modifier le poids des antennes !
    # ------------------------
    
    img.mapsize(512, 0.1)
    img.invert()
    img.mapplot(img.get_map_package(cellsize=0.1))