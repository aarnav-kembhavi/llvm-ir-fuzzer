; Pattern: vector
define <4 x i32> @vector_ops(<4 x i32> %a, <4 x i32> %b) {
entry:
  %add = add <4 x i32> %a, %b
  %mul = mul <4 x i32> %add, <i32 2, i32 2, i32 2, i32 2>
  %elem = extractelement <4 x i32> %mul, i32 0
  %add_elem = add i32 %elem, 5
  %res = insertelement <4 x i32> %mul, i32 %add_elem, i32 0
  ret <4 x i32> %res
}
