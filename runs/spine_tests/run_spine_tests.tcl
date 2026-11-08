# Validate every test spec in runs/spine_tests on cf999, then build a few.
# Run from runs/:   source spine_tests/run_spine_tests.tcl
# Each spec file says, at the top of every spec, which warnings to expect.
#
# cf999 is a comb: a vertical channel at x 5622.5 .. 5704.6, y 3379 .. 14144
# (10765 um), and horizontal channels about 55 um tall from x 0 to 5622, e.g.
# y 10041.1 .. 10095.8. The vertical specs start at y 3500 and fit (8000 um at
# most); h_6stub (6000) and h_8stub (8000) are longer than the 5622 um
# horizontal channel, so they also get HT4-159 (outside the boundary).

read_tech -file ../tech.new.lef
read_lef -file ../ln04lpp_sc_s7p94t_cdk12m3mx2fx7dx_slvt_c60l04.lef
read_def -file cf999.def
foreach f {vertical horizontal warnings errors} {
    read_spine_spec -file spine_tests/$f.yaml
}

set ref INV12M3Mx2Fx7Dx_D112_N_S7P94TSL_C60L04
set vloc {5630 3500}
set hloc {100 10045}

proc try {script} {
    catch {uplevel 1 $script}            ;# errors are printed; keep going
}

foreach spec [get_db spine_spec .name] {
    set horizontal [expr {[get_db spine_spec:$spec .orientation] eq "horizontal"}]
    set loc [expr {$horizontal ? $hloc : $vloc}]
    puts "\n======== $spec"
    try {create_spine -name t_$spec -spec_name $spec -location $loc -validate -ref_cell $ref}
}

# the other build directions
puts "\n======== v_4stub toward -x"
try {create_spine -name t_v_4stub_mx -spec_name v_4stub -location {5700 3500} \
         -build_direction -x -validate -ref_cell $ref}
puts "\n======== h_4stub toward -y"
try {create_spine -name t_h_4stub_my -spec_name h_4stub -location {100 10092} \
         -build_direction -y -validate -ref_cell $ref}

# build: one spec placed twice, and a horizontal one; see them in gui_show
create_spine -name clk_v4_a -spec_name v_4stub -location $vloc -build -ref_cell $ref
create_spine -name clk_v4_b -spec_name v_4stub -location {5630 8000} -build -ref_cell $ref
create_spine -name clk_h4 -spec_name h_4stub -location $hloc -build -ref_cell $ref
puts [get_db spines]

# to look at one before building:
#   create_spine -name t -spec_name v_8stub -location $vloc -validate -show -ref_cell $ref
