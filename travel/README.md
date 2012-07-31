# Travel calculator

Just a quick and dirty Dijkstra's algorithm implementation.

	$ python travel.py travel.yaml malaga manchester

	london madrid
	malaga manchester
	167 ['malaga', 'sevilla', 'gatwick', 'manchester']
	manchester london
	40 ['manchester', 'london']
	london madrid
	133 ['london', 'gatwick', 'madrid']
	total 340.0

While the costs can be written in very simple `yaml` format:

	malaga:
		- sevilla: 10
		- madrid: 60

	sevilla:
		- gatwick: 122

	madrid:
		- gatwick: 83
		- stansted: 93

	gatwick:
		- manchester: 35
		- madrid: 103

	luton:
		- madrid: 104

	stansted:
		- manchester: 30
		- madrid: 120

	manchester:
		- london: 40

	london:
		- stansted: 35
		- gatwick: 30
		- luton: 40

Useful when you're wondering which way it's better and you have lots of options.
You could also use price/time instead of just prices to get the best fit.
