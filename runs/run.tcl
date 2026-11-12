read_tech -file ../tech.new.lef 
read_lef -file ../ln04lpp_sc_s7p94t_cdk12m3mx2fx7dx_slvt_c60l04.lef 
read_spine_spec -file ./custom_spine_vertical.yaml 
read_def -file cf999.def
# Tracks are 0.72 apart; rule1 wires are 0.72 wide with 0.72 spacing, so the
# power (shield) tracks sit 2 tracks (1.44) from each signal track, NA between.
assign_track_for_route -layer IA -net {VDD_SOC NA - NA VSS NA - NA}
assign_track_for_route -layer IB -net {VDD_SOC NA - NA VSS NA - NA}
create_route_rule -name rule1 -layer {IA IB} -width 0.72 -spacing 0.72
# route_pin needs instances: it runs after create_spine below
#route_pin -spec pin_routing_spec.yaml
#create_inst -ref_cell INV12M3Mx2Fx7Dx_D112_N_S7P94TSL_C60L04 -location {5622.772 10066.7}

create_spine -name temp -spec_name custom_spine_v6 -location {5697 10066.7}  -ref_cell INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -build -build_direction {-x} -mirror
# cells onto the legal sites of their LEF SITE (DEF rows), before the pin routes
set_place_constraint -ref_name INV12M3Mx2Fx7Dx_D96_N_S7P94TSL_C60L04 -space_x 3 -space_y 5
legalize_placement -inst [get_db insts]
route_pin -inst [get_db insts .name] -spec pin_routing_spec.yaml
route_net -net [get_db nets .name] -rule rule1 -shield

route_final_stub -stub [get_db stub .name] -rule rule1 -shield


